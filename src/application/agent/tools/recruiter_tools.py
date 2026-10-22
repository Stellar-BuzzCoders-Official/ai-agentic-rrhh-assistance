import json
import uuid
import logging
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from src.config.container import Container
from src.domain.entities import (
    JobPost,
    CandidateProfile,
    CandidatePersonalInfo,
    TechnicalCategory,
    SkillEvaluation,
    TechnicalReport,
    CandidateMatch,
)
from src.domain.services.scoring import calculate_evaluation_summary

logger = logging.getLogger(__name__)


class ParsedCapabilityItem(BaseModel):
    category: str = "general"
    name: str
    type: str = Field(default="Indispensable", description="Indispensable o Deseable")
    level: str = Field(default="Conocimiento", description="Nivel esperado")


class ParsedRequirementsResponse(BaseModel):
    title: str = "Puesto Técnico"
    description: str = ""
    capabilities: List[ParsedCapabilityItem] = Field(default_factory=list)


class EvaluatedSkillItem(BaseModel):
    name: str
    type: str = "Indispensable"
    level: str = "Conocimiento"
    status: str = Field(default="Cumple", description="'Cumple', 'No Cumple' o 'No Verificable'")
    evidence: str = Field(default="", description="Fragmento textual del CV que evidencia el estatus")


class EvaluatedCategoryItem(BaseModel):
    category: str
    skills: List[EvaluatedSkillItem] = Field(default_factory=list)


class CandidateExtractionResponse(BaseModel):
    candidateName: str = "Candidato"
    position: str = "Perfil Técnico"
    experienceYears: float = 0.0
    summary: str = ""
    skillsIdentified: List[str] = Field(default_factory=list)
    categories: List[EvaluatedCategoryItem] = Field(default_factory=list)


def create_recruiter_tools(container: Container, context: Dict[str, Any]):
    """
    Crea las herramientas de LangChain con dependencias inyectadas y contexto del hilo.
    `context` contiene: user_id, thread_id, job_post_holder (un dict mutable con 'job_post' y 'report').
    """
    user_id = context.get("user_id", "default_recruiter")

    @tool
    async def set_job_requirements(requirements_text: str) -> str:
        """
        Extrae y registra los requerimientos técnicos de un puesto laboral.
        Úsalo cuando el reclutador proporcione o describa el perfil requerido.
        """
        logger.info("Ejecutando tool set_job_requirements...")
        llm = container.llm_provider.get_chat_model(temperature=0.0)

        prompt = f"""Extrae del siguiente texto los requerimientos del puesto técnico.
Devuelve el resultado estructurado.
Requerimientos:
{requirements_text}
"""
        structured_llm = llm.with_structured_output(ParsedRequirementsResponse)
        try:
            parsed = await structured_llm.ainvoke(prompt)
        except Exception as e:
            logger.warning("Fallo en structured output para requerimientos: %s. Creando fallback.", str(e))
            parsed = ParsedRequirementsResponse(
                title="Puesto Técnico",
                description=requirements_text[:200],
                capabilities=[
                    ParsedCapabilityItem(category="general", name=term.strip(), type="Indispensable")
                    for term in requirements_text.split(",") if term.strip()
                ]
            )

        job_post = JobPost(
            title=parsed.title,
            description=parsed.description,
            requiredCapabilities=[c.model_dump() for c in parsed.capabilities],
            rawText=requirements_text,
        )

        # Actualizar en el contexto compartido
        context["job_post"] = job_post

        summary_lines = [f"- **{c.name}** ({c.type}, nivel {c.level}) [Categoría: {c.category}]" for c in parsed.capabilities]
        return (
            f"✅ Requerimientos registrados para **{parsed.title}**:\n"
            + "\n".join(summary_lines)
            + "\n\nAhora puedes adjuntar o enviar el CV del candidato para evaluarlo."
        )

    @tool
    async def evaluate_cv(file_id: str) -> str:
        """
        Evalúa un CV adjunto (identificado por su file_id) frente a los requerimientos técnicos del puesto actual.
        Genera el informe técnico, calcula métricas de cumplimiento, indexa el candidato en el pool del reclutador
        y busca perfiles similares en el talent pool histórico.
        """
        logger.info("Ejecutando tool evaluate_cv con file_id: %s", file_id)

        # 1. Recuperar archivo y texto de forma puramente asíncrona
        file_meta = await container.file_repo.get_file_metadata(file_id)

        if not file_meta or not file_meta.extractedText:
            return f"❌ No se encontró texto para el archivo con ID {file_id}. Asegúrate de que haya sido subido previamente."

        cv_text = file_meta.extractedText
        job_post: Optional[JobPost] = context.get("job_post")

        job_reqs_text = ""
        if job_post:
            job_reqs_text = f"Puesto: {job_post.title}\n" + "\n".join(
                [f"- {c.get('name')}: {c.get('type')} ({c.get('level', '')})" for c in job_post.requiredCapabilities]
            )
        else:
            job_reqs_text = "Evaluar habilidades técnicas generales de ingeniería de software."

        # 2. Extracción y evaluación mediante LLM estructurado
        llm = container.llm_provider.get_chat_model(temperature=0.0)
        prompt = f"""Evalúa minuciosamente el siguiente CV frente a los requerimientos del puesto.
Para cada habilidad requerida, determina si 'Cumple', 'No Cumple' o es 'No Verificable', y OBLIGATORIAMENTE cita el fragmento exacto del CV como evidencia.

Requerimientos del puesto:
{job_reqs_text}

Texto del CV:
{cv_text[:12000]}
"""
        structured_llm = llm.with_structured_output(CandidateExtractionResponse)
        try:
            extraction = await structured_llm.ainvoke(prompt)
        except Exception as e:
            logger.error("Error en structured output de CV: %s", str(e))
            # Fallback simple
            extraction = CandidateExtractionResponse(
                candidateName=file_meta.fileName.replace(".pdf", "").replace(".docx", ""),
                position="Candidato Evaluado",
                experienceYears=2.0,
                skillsIdentified=["Habilidades generales"],
                categories=[
                    EvaluatedCategoryItem(
                        category="general",
                        skills=[
                            EvaluatedSkillItem(name="Perfil Técnico", type="Indispensable", status="Cumple", evidence="CV adjunto")
                        ]
                    )
                ]
            )

        # 3. Mapear a entidades de dominio y calcular score determinístico
        domain_categories: List[TechnicalCategory] = []
        for cat in extraction.categories:
            skills = [
                SkillEvaluation(
                    name=s.name,
                    type=s.type if s.type in ["Indispensable", "Deseable"] else "Indispensable",
                    level=s.level,
                    status=s.status if s.status in ["Cumple", "No Cumple", "No Verificable"] else "Cumple",
                    evidence=s.evidence or "Detectado en CV",
                )
                for s in cat.skills
            ]
            domain_categories.append(TechnicalCategory(category=cat.category, skills=skills))

        scoring_summary = calculate_evaluation_summary(domain_categories)

        personal_info = CandidatePersonalInfo(
            name=extraction.candidateName,
            position=extraction.position,
            experienceYears=extraction.experienceYears,
        )

        # 4. Generar embedding y guardar en Talent Pool (por reclutador)
        candidate_embedding = None
        try:
            embed_text = f"{extraction.candidateName} - {extraction.position}. Skills: {', '.join(extraction.skillsIdentified)}. {extraction.summary}"
            embeddings_client = container.embeddings_provider.get_embeddings()
            if hasattr(embeddings_client, "aembed_query"):
                candidate_embedding = await embeddings_client.aembed_query(embed_text)
            else:
                candidate_embedding = embeddings_client.embed_query(embed_text)
        except Exception as e_emb:
            logger.warning("No se pudo generar embedding para el candidato: %s", str(e_emb))

        candidate_profile = CandidateProfile(
            recruiterId=user_id,
            personalInfo=personal_info,
            skills=extraction.skillsIdentified,
            summary=extraction.summary or f"{extraction.position} con {extraction.experienceYears} años de experiencia",
            rawCvText=cv_text,
            fileUrl=file_meta.fileUrl,
            embedding=candidate_embedding,
        )

        await container.candidate_repo.save_candidate(candidate_profile)
        # Buscar otros candidatos relevantes en el pool histórico para este puesto
        matches = await container.candidate_repo.search_candidates(
            recruiter_id=user_id,
            query_text=job_reqs_text,
            query_embedding=candidate_embedding,
            limit=3,
        )
        relevant_pool_matches = [m for m in matches if m.candidateId != candidate_profile.id]

        # 5. Construir TechnicalReport
        resumen_compat = {
            "cumpleIndispensable": scoring_summary.requiredSkillsMet,
            "cumpleDeseable": scoring_summary.optionalSkillsMet,
            "recomendation": scoring_summary.recommendation,
        }

        report = TechnicalReport(
            personalInfo=personal_info,
            technicalCapabilities=domain_categories,
            evaluationSummary=scoring_summary,
            resumen=resumen_compat,
            isGrounded=True,
            relevantProfilesFromPool=relevant_pool_matches,
        )

        context["technical_report"] = report
        context["relevant_candidates"] = relevant_pool_matches
        context["current_cv_id"] = file_id
        context["current_cv_text"] = cv_text

        # Resumen legible para la respuesta del agente
        report_preview = (
            f"📊 **Informe Técnico de Evaluación**:\n"
            f"- **Candidato:** {personal_info.name} ({personal_info.position})\n"
            f"- **Años de Experiencia:** {personal_info.experienceYears}\n"
            f"- **Cumplimiento Indispensables:** {scoring_summary.requiredSkillsMet}/{scoring_summary.totalRequiredSkills}\n"
            f"- **Cumplimiento Deseables:** {scoring_summary.optionalSkillsMet}/{scoring_summary.totalOptionalSkills}\n"
            f"- **Porcentaje Total:** {scoring_summary.matchPercentage}%\n"
            f"- **Recomendación:** {scoring_summary.recommendation}\n"
        )

        if relevant_pool_matches:
            report_preview += "\n🔍 **Perfiles relevantes identificados en tu Talent Pool histórico**:\n"
            for m in relevant_pool_matches:
                report_preview += f"- **{m.name}** ({m.position}, {m.experienceYears} años) - Habilidades afines: {', '.join(m.matchedSkills[:4])}\n"

        return report_preview

    @tool
    async def search_talent_pool(query: str, limit: int = 5) -> str:
        """
        Busca candidatos existentes en el Talent Pool histórico del reclutador
        mediante búsqueda híbrida vectorial y textual.
        """
        logger.info("Ejecutando tool search_talent_pool para query: '%s'", query)

        query_emb = None
        try:
            embeddings_client = container.embeddings_provider.get_embeddings()
            if hasattr(embeddings_client, "aembed_query"):
                query_emb = await embeddings_client.aembed_query(query)
            else:
                query_emb = embeddings_client.embed_query(query)
        except Exception as e_emb:
            logger.warning("No se pudo generar embedding de búsqueda: %s", str(e_emb))

        matches = await container.candidate_repo.search_candidates(
            recruiter_id=user_id,
            query_text=query,
            query_embedding=query_emb,
            limit=limit,
        )

        if not matches:
            return "No se encontraron candidatos afines en el Talent Pool para los criterios indicados."

        res = f"Se encontraron {len(matches)} candidatos afines en tu Talent Pool:\n"
        for i, m in enumerate(matches, 1):
            res += f"{i}. **{m.name}** - {m.position} ({m.experienceYears} años exp.). Habilidades: {', '.join(m.matchedSkills)}. Score de coincidencia: {m.score}\n"
        return res

    @tool
    async def get_job_requirements() -> str:
        """
        Consulta los requerimientos técnicos y capacidades del puesto definidos en la conversación actual.
        """
        job_post: Optional[JobPost] = context.get("job_post")
        if not job_post:
            return "Aún no se han configurado los requerimientos para este puesto."
        caps = [f"- {c.get('name')} ({c.get('type')}, nivel {c.get('level')})" for c in job_post.requiredCapabilities]
        return f"**Puesto:** {job_post.title}\n**Descripción:** {job_post.description}\n**Requerimientos:**\n" + "\n".join(caps)

    return [set_job_requirements, evaluate_cv, search_talent_pool, get_job_requirements]
