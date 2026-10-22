import logging
from typing import Optional, List
from src.application.ports.outbound import CandidateRepositoryPort
from src.domain.entities import CandidateProfile, CandidateMatch
from src.infrastructure.persistence.cosmos.client import CosmosDBManager
from src.infrastructure.persistence.memory.memory_repos import _cosine_similarity
from src.config.settings import settings

logger = logging.getLogger(__name__)


class CosmosCandidateRepository(CandidateRepositoryPort):
    def __init__(self, manager: CosmosDBManager | None = None):
        self.manager = manager or CosmosDBManager.get_instance()
        self.container_name = settings.COSMOS_CANDIDATES_CONTAINER

    async def save_candidate(self, candidate: CandidateProfile) -> CandidateProfile:
        container = self.manager.get_container(self.container_name)
        doc = candidate.model_dump(by_alias=True)
        # Cosmos requiere id único como string
        doc["id"] = candidate.id
        doc["recruiterId"] = candidate.recruiterId
        # Cosmos DB rechaza estrictamente 'ttl': null. Si no se especifica un ttl entero o -1, se remueve.
        if doc.get("ttl") is None:
            doc.pop("ttl", None)
        container.upsert_item(doc)
        logger.info("Candidato guardado en Cosmos DB: %s (recruiterId: %s)", candidate.personalInfo.name, candidate.recruiterId)
        return candidate

    async def get_candidate(self, candidate_id: str, recruiter_id: str) -> Optional[CandidateProfile]:
        container = self.manager.get_container(self.container_name)
        try:
            item = container.read_item(item=candidate_id, partition_key=recruiter_id)
            return CandidateProfile(**item)
        except Exception as e:
            logger.debug("Candidato no encontrado en Cosmos DB: %s", str(e))
            return None

    async def search_candidates(
        self,
        recruiter_id: str,
        query_text: str,
        query_embedding: Optional[List[float]] = None,
        limit: int = 5,
    ) -> List[CandidateMatch]:
        container = self.manager.get_container(self.container_name)

        # 1. Intentar consulta de búsqueda vectorial nativa en Cosmos DB NoSQL
        if query_embedding:
            try:
                vector_query = (
                    "SELECT TOP @limit c.id, c.personalInfo, c.skills, c.summary, c.fileUrl, "
                    "VectorDistance(c.embedding, @query_embedding) AS similarityScore "
                    "FROM c "
                    "WHERE c.recruiterId = @recruiterId "
                    "ORDER BY VectorDistance(c.embedding, @query_embedding)"
                )
                parameters = [
                    {"name": "@limit", "value": limit},
                    {"name": "@query_embedding", "value": query_embedding},
                    {"name": "@recruiterId", "value": recruiter_id},
                ]
                items = list(container.query_items(
                    query=vector_query,
                    parameters=parameters,
                    partition_key=recruiter_id,
                ))

                results = []
                for item in items:
                    info = item.get("personalInfo", {})
                    skills = item.get("skills", [])
                    matched_skills = [s for s in skills if s.lower() in query_text.lower()]
                    sim_score = float(item.get("similarityScore", 0.0))
                    # Normalizar a similitud [0, 1] si la distancia es coseno (distancia = 1 - similitud)
                    score = max(0.0, min(1.0, 1.0 - sim_score))

                    results.append(
                        CandidateMatch(
                            candidateId=item["id"],
                            name=info.get("name", "Candidato"),
                            position=info.get("position", "Perfil"),
                            experienceYears=float(info.get("experienceYears", 0.0)),
                            matchedSkills=matched_skills or skills[:3],
                            missingSkills=[],
                            score=round(score, 3),
                            summary=item.get("summary", ""),
                            fileUrl=item.get("fileUrl"),
                        )
                    )
                if results:
                    return results
            except Exception as e:
                logger.warning("Búsqueda vectorial nativa de Cosmos no disponible o falló: %s. Aplicando búsqueda por escaneo en partición.", str(e))

        # 2. Fallback: recuperación de candidatos del reclutador y ranking híbrido
        query = "SELECT * FROM c WHERE c.recruiterId = @recruiterId"
        parameters = [{"name": "@recruiterId", "value": recruiter_id}]
        items = list(container.query_items(query=query, parameters=parameters, partition_key=recruiter_id))

        query_terms = set(query_text.lower().split())
        scored_candidates = []

        for item in items:
            candidate = CandidateProfile(**item)
            score = 0.0
            if query_embedding and candidate.embedding:
                score = _cosine_similarity(query_embedding, candidate.embedding)
            else:
                cand_terms = set(candidate.rawCvText.lower().split()) | {s.lower() for s in candidate.skills}
                overlap = len(query_terms.intersection(cand_terms))
                score = overlap / max(len(query_terms), 1)

            scored_candidates.append((score, candidate))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        top = scored_candidates[:limit]

        final_results = []
        for score, cand in top:
            matched_skills = [s for s in cand.skills if s.lower() in query_text.lower()]
            final_results.append(
                CandidateMatch(
                    candidateId=cand.id,
                    name=cand.personalInfo.name,
                    position=cand.personalInfo.position,
                    experienceYears=cand.personalInfo.experienceYears,
                    matchedSkills=matched_skills or cand.skills[:3],
                    missingSkills=[],
                    score=round(score, 3),
                    summary=cand.summary,
                    fileUrl=cand.fileUrl,
                )
            )
        return final_results

    async def delete_candidate(self, candidate_id: str, recruiter_id: str) -> bool:
        container = self.manager.get_container(self.container_name)
        try:
            container.delete_item(item=candidate_id, partition_key=recruiter_id)
            return True
        except Exception as e:
            logger.error("Error al borrar candidato de Cosmos DB: %s", str(e))
            return False
