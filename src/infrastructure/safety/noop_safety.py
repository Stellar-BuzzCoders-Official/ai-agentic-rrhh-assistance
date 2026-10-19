from typing import Tuple
from src.application.ports.outbound import ContentSafetyPort


class NoopContentSafetyAdapter(ContentSafetyPort):
    """Adaptador de seguridad no-op para desarrollo y pruebas."""

    async def check_input(self, text: str) -> Tuple[bool, str]:
        # Siempre seguro
        return True, ""
