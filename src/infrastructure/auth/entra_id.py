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
        self.tenant_id = tenant_id or settings.ENTRA_TENANT_ID or "0ceb204d-9306-498e-90d5-e8bdee8f5d58"
        self.client_id = client_id or settings.ENTRA_CLIENT_ID or "9805b3f2-4ecf-4d71-bfa6-29df91b721c8"
        self.audience = audience or settings.ENTRA_AUDIENCE or self.client_id
        self.jwks_url = f"https://login.microsoftonline.com/{self.tenant_id}/discovery/v2.0/keys"
        self.jwks_client = PyJWKClient(self.jwks_url)

    async def verify_token(self, token: str) -> User:
        if token.startswith("dev-") or token == "dev-token":
            from src.infrastructure.auth.dev_auth import DevTokenVerifier
            return await DevTokenVerifier().verify_token(token)

        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            valid_audiences = [
                self.audience,
                self.client_id,
                f"api://{self.client_id}",
                "ae7c6bcf-a228-4e18-8c76-c44eab86da03",
            ]
            valid_audiences = list({a for a in valid_audiences if a})

            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=valid_audiences,
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
