from abc import ABC, abstractmethod

class ConversationManagementPort(ABC):
    @abstractmethod
    def new_chat(self, data: dict) -> dict:
        """Inicia una nueva conversación y limpia la caché."""
        pass

    @abstractmethod
    def save_conversation(self, conversation_id: str, user_story: str, name_history: str, is_valid_user_story: bool):
        """Guarda la información de la conversación en el historial."""
        pass
