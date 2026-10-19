# src/ports/test_cases_ports/process_context_port.py
from abc import ABC, abstractmethod

class ProcessRequestRequirementsPort(ABC):
    @abstractmethod
    def _process_request_requirements(
        self,
        input_data: dict,
        conversation_id: str,
        user_message: str,
        previous_messages: list,
        
    ) -> tuple:
        """Procesa el contexto del usuario y genera una respuesta."""
        pass

    @abstractmethod
    def validate_request_requirements(self, context: str) -> bool:
        """Valida el contexto proporcionado por el usuario."""
        pass

    @abstractmethod
    def prompt_validation_request_requirements(self, context: str) -> str:
        """Genera un prompt para validar el contexto."""
        pass
