from abc import ABC, abstractmethod

class ProcessRequestCvPort(ABC):
    @abstractmethod
    def _process_request_cv(self,
        input_data: dict,
        conversation_id: str,
        user_message: str,
        previous_messages: list,
        
    ) -> tuple:
        """Procesa el contexto del usuario y genera una respuesta."""
        pass

    @abstractmethod
    def validate_request_cv(self, request_cv: str) -> bool:
        """Valida si una historia de usuario cumple con los criterios establecidos."""
        pass

    @abstractmethod
    def prompt_validation_request_cv(self, request_cv: str) -> str:
        """Genera un prompt para validar una historia de usuario."""
        pass
