from abc import ABC, abstractmethod

class NameHistoryGeneratorPort(ABC):
    @abstractmethod
    def generate_name_history(self, context_data: str) -> str:
        """Genera un nombre basado en el contexto proporcionado."""
        pass
