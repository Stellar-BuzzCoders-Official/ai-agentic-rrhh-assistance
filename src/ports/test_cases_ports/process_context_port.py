# src/ports/test_cases_ports/process_context_port.py
from abc import ABC, abstractmethod

class ProcessContextPort(ABC):
    @abstractmethod
    def _process_context(
        self,
        input_data: dict,
        conversation_id: str,
        user_message: str,
        previous_messages: list,
        
    ) -> tuple:
        """Procesa el contexto del usuario y genera una respuesta."""
        pass

    @abstractmethod
    def validate_context(self, context: str) -> bool:
        """Valida el contexto proporcionado por el usuario."""
        pass

    @abstractmethod
    def prompt_validation_context(self, context: str) -> str:
        """Genera un prompt para validar el contexto."""
        pass
