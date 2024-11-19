from abc import ABC, abstractmethod

class LLMPort(ABC):
    @abstractmethod
    def generate_response(self, prompt: str, conversation_id: str = None) -> tuple[str, str]:
        pass
