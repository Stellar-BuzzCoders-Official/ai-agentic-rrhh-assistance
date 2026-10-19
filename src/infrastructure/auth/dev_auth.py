import logging
from src.application.ports.outbound import TokenVerifierPort
from src.domain.entities import User
from src.config.settings import settings

logger = logging.getLogger(__name__)


class DevTokenVerifier(TokenVerifierPort):
    """
    Verificador de tokens para desarrollo local y tests automatizados.
    Acepta cualquier token no vacío o cadenas tipo 'dev-token', 'Bearer mock-token'.
    """

    async def verify_token(self, token: str) -> User:
        if not token or not token.strip():
            raise ValueError("Token no proporcionado.")

        user_id = settings.DEV_AUTH_USER_ID
        clean_token = token.replace("Bearer ", "").strip()
        if clean_token.startswith("token-") or clean_token.startswith("user-"):
            user_id = clean_token

        return User(
            id=user_id,
            email=f"{user_id}@joyit.ai",
            name=f"User {user_id}",
            role="recruiter",
            isActive=True,
        )
