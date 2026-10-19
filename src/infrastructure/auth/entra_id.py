import logging
import jwt
from jwt import PyJWKClient
from src.application.ports.outbound import TokenVerifierPort
from src.domain.entities import User
from src.config.settings import settings

logger = logging.getLogger(__name__)


class EntraIDTokenVerifier(TokenVerifierPort):
    def __init__(
        self,
        tenant_id: str | None = None,
        client_id: str | None = None,
        audience: str | None = None,
    ):
        self.tenant_id = tenant_id or settings.ENTRA_TENANT_ID or "common"
        self.client_id = client_id or settings.ENTRA_CLIENT_ID
        self.audience = audience or settings.ENTRA_AUDIENCE or self.client_id
        self.jwks_url = f"https://login.microsoftonline.com/{self.tenant_id}/discovery/v2.0/keys"
        self.jwks_client = PyJWKClient(self.jwks_url)

    async def verify_token(self, token: str) -> User:
        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.audience,
                options={"verify_exp": True},
            )

            user_id = payload.get("oid") or payload.get("sub")
            email = payload.get("preferred_username") or payload.get("email") or f"{user_id}@entra.local"
            name = payload.get("name") or email.split("@")[0]
            roles = payload.get("roles", [])
            role = "admin" if "Admin" in roles else "recruiter"

            return User(
                id=user_id,
                email=email,
                name=name,
                role=role,
                isActive=True,
            )
        except Exception as e:
            logger.error("Error al validar token de Microsoft Entra ID: %s", str(e))
            raise ValueError(f"Token de Entra ID inválido: {str(e)}")
