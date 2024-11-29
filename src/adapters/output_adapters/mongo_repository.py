from src.ports.output_ports.mongo_port import MongoDBPort
from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError
from bson import ObjectId 
from typing import List
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MongoDBRepository(MongoDBPort):
    def __init__(self):
        mongo_user = os.getenv('MONGO_INITDB_ROOT_USERNAME', 'root')
        mongo_password = os.getenv('MONGO_INITDB_ROOT_PASSWORD', 'rootpassword')
        mongo_host = os.getenv('MONGO_SERVER_HOST', 'localhost')
        mongo_port = os.getenv('MONGO_SERVER_PORT', '28018')
        self.logger = logging.getLogger(__name__)
        self.loggin = logging.getLogger(__name__)
        self.loggin.info("Conectando a MongoDB...")
        self.loggin.info(f"Host: {mongo_host}, Port: {mongo_port}, User: {mongo_user}")
        self.loggin.info(f"Password: {'*' * len(mongo_password)}")
        
        self.mongo_uri = f'mongodb://{mongo_user}:{mongo_password}@{mongo_host}:{mongo_port}/'
        self.client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
        self.db = self.client['mongo_db']
        self.collection_conversation = self.db['conversations']
        self.logger.info("collection conversations creado")
        self.collection_user = self.db['users']
        self.logger.info("collection users creado")
        self.collection_file = self.db['capabilities']
        self.logger.info("collection files creado")
        logger.info("Conexión a MongoDB establecida.")

    def save_conversation(self, conversation: dict):
        self.logger.info(f"Intentando guardar la conversacion: {conversation}")
        try:
            if 'data' not in conversation or 'conversationId' not in conversation['data']:
                raise ValueError("El conversacion debe contener la clave 'data' y 'conversationId'.")
            
            # Si el _id está presente, actualiza el documento, si no, lo inserta
            result = self.collection_conversation.update_one(
                {"_id": conversation["_id"]},  
                {"$set": conversation},         
                upsert=True                
            )
            
            if result.matched_count > 0:
                self.logger.info(f"[MONGO] conversacion actualizado con _id: {conversation['_id']}")
            elif result.upserted_id is not None:
                self.logger.info(f"[MONGO] Nuevo conversacion insertado con _id: {conversation['_id']}")

        except PyMongoError as e:
            self.logger.error(f"[MONGO] Error al guardar conversacion: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"[MONGO] Error inesperado: {str(e)}")
            raise
            
    def update_conversation_context(self, conversation: dict):
        """
        Actualiza un documento existente en MongoDB usando el _id como identificador
        """
        try:
            result = self.collection_conversation.replace_one(
                {"_id": conversation["_id"]},
                conversation,                   
                upsert=True             
            )
            return result.modified_count > 0
        except PyMongoError as e:
            self.logger.error(f"[MONGO] Error al actualizar conversacion: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Error inesperado al actualizar conversacion: {str(e)}")
            raise

    def update_conversation_user_story(self, conversation_id, update_fields):
        """
        Actualiza la conversación en MongoDB, sin incluir el campo nameHistory.

        Args:
            conversation_id (str): ID de la conversación a actualizar.
            update_fields (dict): Campos a actualizar en la conversación.
        """
        result = self.collection_conversation.update_one(
            {"_id": conversation_id}, 
            {"$set": update_fields}
        )
        return result.modified_count > 0  
        
    def delete_conversation(self, conversation_id: str):
        """Elimina un conversacion de MongoDB usando un UUID."""
        try:
            
            return self.collection_conversation.delete_one({"_id": conversation_id})
        except Exception as e:
            raise PyMongoError(f"Error al eliminar el conversacion con _id {conversation_id}: {str(e)}")
    
    def delete_history_conversation(self, user_id: str):
        """
        Elimina todos los documentos de la colección 'conversations' para un usuario específico.
        
        Args:
            user_id (str): El _id del usuario cuyas conversaciones se eliminarán.
        """
        try:
            result = self.collection_conversation.delete_many({"data.userID": user_id})
            
            if result is not None and hasattr(result, 'deleted_count'):
                self.logger.info(f"Se han eliminado {result.deleted_count} conversaciones del usuario con _id {user_id}.")
                return {"message": f"Se han eliminado {result.deleted_count} conversaciones del usuario con _id {user_id}."}, 200
            else:
                self.logger.error(f"Error al eliminar el historial de conversaciones para el usuario con _id {user_id}: operación fallida o no hay conversaciones.")
                return {"error": f"Error al eliminar el historial de conversaciones para el usuario con _id {user_id}: operación fallida o no hay conversaciones."}, 404
        except PyMongoError as e:
            self.logger.error(f"Error al eliminar el historial de conversaciones para el usuario con _id {user_id}: {str(e)}")
            return {"error": f"Error al eliminar el historial de conversaciones para el usuario con _id {user_id}: {str(e)}"}, 500

    def get_conversation_by_id(self, conversation_id: str) -> dict:
        """
        Buscar un conversacion por su _id en MongoDB (UUID).
        """
        try:
            conversation = self.collection_conversation.find_one({"_id": conversation_id})  # Usar conversation_id directamente
            if conversation:
                return conversation
            else:
                raise ValueError(f"conversacion con ID {conversation_id} no encontrado.")
        except Exception as e:
            self.logger.error(f"Error al obtener el conversacion por ID: {str(e)}")
            raise
        
    def get_all_conversations(self, user_id: str) -> list:
        """
        Recupera todas las conversaciones de un usuario específico de la colección 'conversations'.
        
        Args:
            user_id (str): El _id del usuario cuyas conversaciones se recuperarán.
        
        Returns:
            list: Una lista de todas las conversaciones del usuario.
        """
        try:
            conversations = list(self.collection_conversation.find({"data.userID": user_id}))
            self.logger.info(f"Se han recuperado {len(conversations)} conversaciones del usuario con _id {user_id} de MongoDB.")
            return conversations
        except PyMongoError as e:
            self.logger.error(f"Error al recuperar las conversaciones del usuario con _id {user_id} de MongoDB: {str(e)}")
            raise
    
    def get_user_by_id(self, user_id: str) -> dict:
        """
        Recupera un usuario específico de la colección 'users' por su _id.
        
        Args:
            user_id (str): El _id del usuario a recuperar.
        
        Returns:
            dict: Los datos del usuario o None si no se encuentra.
        """
        try:
            user = self.collection_user.find_one({"_id": user_id})
            if user:
                self.logger.info(f"Se ha recuperado el usuario con _id {user_id} de MongoDB.")
            else:
                self.logger.info(f"No se encontró ningún usuario con _id {user_id} en MongoDB.")
            return user
        except PyMongoError as e:
            self.logger.error(f"Error al recuperar el usuario con _id {user_id} de MongoDB: {str(e)}")
            raise

    def get_context_conversations(self, conversation_id: str) -> list:
        """Recupera los conversacions de contexto de MongoDB basados en el conversation_id."""
        
        query = {"data.conversationId": conversation_id}
        projection = {"_id": 0}  # Excluye '_id' de la respuesta
        
        result = list(self.db['conversations'].find(query, projection))

        # Imprimir el resultado para verificar que no incluye el campo '_id'
        print(result)
        
        return result
    
    def save_user(self, user_data: dict):
        """
        Guarda o actualiza la información del usuario en la colección 'users'.
        """
        try:
            user_id = user_data.get('userID')
            if not user_id:
                raise ValueError("El 'userId' es obligatorio para guardar un usuario.")
            
            # Insertar o actualizar el documento en la colección 'users'
            result = self.collection_user.update_one(
                {"_id": user_id},  # Filtro para encontrar el documento (userId como _id)
                {"$set": user_data},  # Actualizar los campos con la información del usuario
                upsert=True  # Insertar si no existe
            )

            if result.matched_count > 0:
                self.logger.info(f"[MONGO] Usuario actualizado con _id: {user_id}")
            elif result.upserted_id is not None:
                self.logger.info(f"[MONGO] Nuevo usuario insertado con _id: {user_id}")
        except PyMongoError as e:
            self.logger.error(f"[MONGO] Error al guardar usuario: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"[MONGO] Error inesperado al guardar usuario: {str(e)}")
            raise
    
    def get_all_users(self) -> List[dict]:
        """
        Recupera todos los usuarios de la colección 'users'.
        """
        try:
            users = list(self.collection_user.find())  # Recupera todos los documentos de la colección 'users'
            self.logger.info(f"Se han recuperado {len(users)} usuarios de MongoDB.")
            return users
        except PyMongoError as e:
            self.logger.error(f"Error al recuperar todos los usuarios de MongoDB: {str(e)}")
            raise
    
    def find_one(self, collection: str, query: dict):
        """
        Encuentra un documento en la colección especificada que coincida con el query dado.

        :param collection: Nombre de la colección
        :param query: Diccionario de consulta
        :return: Documento encontrado o None si no se encuentra
        """
        return self.db[collection].find_one(query)
    
    def delete_all_users(self) -> int:
        """
        Borra todos los usuarios de la colección 'users'.
        
        Returns:
            int: El número de usuarios borrados.
        """
        try:
            result = self.collection_user.delete_many({})
            deleted_count = result.deleted_count
            self.logger.info(f"[MONGO] Se han borrado {deleted_count} usuarios de la colección 'users'.")
            return deleted_count
        except PyMongoError as e:
            self.logger.error(f"[MONGO] Error al borrar todos los usuarios: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"[MONGO] Error inesperado al borrar todos los usuarios: {str(e)}")
            raise