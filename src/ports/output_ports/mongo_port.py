# src/ports/mongo_port.py

from abc import ABC, abstractmethod
from typing import List

class MongoDBPort(ABC):
    @abstractmethod
    def save_conversation(self, conversation: dict):
        """Guarda una conversacion en MongoDB."""
        pass
        
    @abstractmethod
    def get_conversation_by_id(self, conversation_id: str) -> dict:
        """Recupera una conversacion de MongoDB por su ID."""
        pass
    
    @abstractmethod
    def get_all_conversations(self) -> list:
        """Recupera todos las conversacions de MongoDB."""
        pass
        
    @abstractmethod
    def get_context_conversations(self, conversation_id: str) -> List[dict]:
        """
        Recupera las conversacions de contexto para una conversation_id dado.
        
        Args:
            conversation_id (str): El ID de la conversación.
        
        Returns:
            List[dict]: unaa lista de conversacions de contexto.
        """
        pass
    @abstractmethod
    def update_conversation_context(self, conversation: dict):
        """Actualiza una conversacion en MongoDB."""

    @abstractmethod
    def update_conversation_user_story(self, conversation_id, update_fields):
        pass
    @abstractmethod
    def delete_history_conversation(self):
        """Elimina todos los conversaciones de la colección."""
        pass
    @abstractmethod
    def save_user(self, user_data: dict):
        """Guarda o actualiza la información del usuario en la colección 'users'."""
        pass
    @abstractmethod
    def get_all_users(self) -> List[dict]:
        """Recupera todos los usuarios de la colección 'users'."""
        pass
    @abstractmethod
    def find_one(self, collection: str, query: dict):
        """Encuentra un documento en la colección especificada que coincida con el query dado.

        :param collection: Nombre de la colección
        :param query: Diccionario de consulta
        :return: Documento encontrado o None si no se encuentra"""
        pass