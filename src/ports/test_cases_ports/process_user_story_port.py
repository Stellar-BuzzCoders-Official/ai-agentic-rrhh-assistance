from abc import ABC, abstractmethod

class ProcessUserStoryPort(ABC):
    @abstractmethod
    def _process_user_story(self, input_data) -> dict:
        """Procesa una historia de usuario y genera casos de prueba."""
        pass

    @abstractmethod
    def validate_user_story(self, user_story: str) -> bool:
        """Valida si una historia de usuario cumple con los criterios establecidos."""
        pass

    @abstractmethod
    def prompt_validation_user_story(self, user_story: str) -> str:
        """Genera un prompt para validar una historia de usuario."""
        pass
