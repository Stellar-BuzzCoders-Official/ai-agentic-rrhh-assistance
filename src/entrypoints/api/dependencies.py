import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.config.container import Container
from src.domain.entities import User

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


def get_container() -> Container:
    return Container.get_instance()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    container: Container = Depends(get_container),
) -> User:
    """
    Verifica el token Bearer emitido por Microsoft Entra ID (o token de desarrollo).
    Garantiza que el usuario exista en el repositorio de usuarios (auto-alta).
    """
    if not credentials or not credentials.credentials:
        # En modo DEV o HYBRID permitimos fallback al usuario mock si no hay auth header
        from src.config.settings import settings
        if settings.AUTH_PROVIDER in ("dev", "hybrid"):
            user = await container.token_verifier.verify_token("dev-token")
            await container.user_repo.save_user(user)
            return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere token de autorización Bearer de Microsoft Entra ID",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        user = await container.token_verifier.verify_token(token)
        # Asegurar persistencia del usuario
        existing = await container.user_repo.get_user_by_id(user.id)
        if not existing:
            await container.user_repo.save_user(user)
        return user
    except Exception as e:
        logger.error("Fallo de autenticación: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token de autenticación no válido: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
