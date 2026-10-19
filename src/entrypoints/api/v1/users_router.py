from fastapi import APIRouter, Depends
from src.entrypoints.api.dependencies import get_current_user
from src.domain.entities import User

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.get("/me", response_model=User)
async def get_my_profile(current_user: User = Depends(get_current_user)):
    """Retorna la información del usuario actualmente autenticado con Microsoft Entra ID."""
    return current_user
