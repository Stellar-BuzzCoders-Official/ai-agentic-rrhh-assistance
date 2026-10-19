# src/adapters/conversation_management_adapter.py

import logging
from src.ports.conversation_ports.conversation_management_port import ConversationManagementPort
from src.ports.output_ports.mongo_port import MongoDBPort

class ConversationManagementAdapter(ConversationManagementPort):
    def __init__(self, mongo_repo: MongoDBPort):
        self.mongo_repo = mongo_repo
        self.conversation_history = {}
        self.logger = logging.getLogger(__name__)

    def new_chat(self, data) -> str:
        """Inicia una nueva conversación y limpia la caché."""
        conversation_id = data.get('conversationId')
        
        if not conversation_id:
            return {"error": "Missing conversationId."}, 400

        # Limpiar la caché de la conversación
        if conversation_id in self.conversation_history:
            del self.conversation_history[conversation_id]  

        # Inicializar un nuevo estado de conversación
        self.conversation_history[conversation_id] = []  # O inicializa como prefieras

        return {"message": "New chat started and cache cleared.", "conversationId": conversation_id}

    def save_conversation(self, conversation_id, user_story, name_history, is_valid_user_story):
        if isinstance(conversation_id, str):
            self.conversation_history[conversation_id] = {
                "user_story": user_story,
                "name_history": name_history,
                "is_valid": is_valid_user_story
            }
        else:
            # Manejar el caso donde conversation_id no es un string
            logging.error("El conversation_id no es un string: {}".format(conversation_id))