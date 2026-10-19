import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.entrypoints.api.dependencies import get_current_user, get_container
from src.config.container import Container
from src.domain.entities import User, CandidateMatch, CandidateProfile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/candidates", tags=["Candidates Talent Pool"])


@router.get("", response_model=List[CandidateMatch])
async def search_candidates(
    q: str = Query(..., description="Consulta de búsqueda técnica o requisitos (ej. 'Python FastAPI Azure')"),
    limit: int = Query(default=5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """
    Búsqueda híbrida (vectorial + texto completo) de perfiles en el Talent Pool
    aislado por reclutador.
    """
    query_emb = None
    try:
        query_emb = container.embeddings_provider.get_embeddings().embed_query(q)
    except Exception as e:
        logger.warning("Fallo al generar embedding para búsqueda: %s", str(e))

    return await container.candidate_repo.search_candidates(
        recruiter_id=current_user.id,
        query_text=q,
        query_embedding=query_emb,
        limit=limit,
    )


@router.get("/{candidate_id}")
async def get_candidate_detail(
    candidate_id: str,
    current_user: User = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """Recupera los datos estructurados y el extracto de un candidato por su ID."""
    candidate = await container.candidate_repo.get_candidate(candidate_id, current_user.id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidato no encontrado en tu talent pool")
    return candidate


@router.delete("/{candidate_id}")
async def delete_candidate(
    candidate_id: str,
    current_user: User = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """
    Elimina un candidato del Talent Pool del reclutador (ejercicio de derechos ARCO /
    derecho de supresión de datos personales).
    """
    deleted = await container.candidate_repo.delete_candidate(candidate_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Candidato no encontrado para eliminar")
    return {"message": f"Candidato {candidate_id} eliminado exitosamente."}
