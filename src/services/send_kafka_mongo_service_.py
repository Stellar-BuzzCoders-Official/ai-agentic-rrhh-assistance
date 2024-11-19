from kafka import KafkaConsumer
import json
from pymongo import MongoClient
from datetime import datetime

TOPIC = 'test'
KAFKA_SERVER = 'localhost:29092'

class SendKafkaMongoService:

    def __ini__(self, conversations_collection):
        
        self.conversations_collection = conversations_collection
        
    # Consumir mensajes de Kafka y almacenarlos en MongoDB
    def consume_messages(self,):
        consumer = KafkaConsumer(
            TOPIC,
            bootstrap_servers=KAFKA_SERVER,
            auto_offset_reset='earliest',
            group_id='my-python-group'
        )
        
        print("Esperando mensajes de Kafka...")
        
        for message in consumer:
            message_value = message.value.decode('utf-8')
            message_json = json.loads(message_value)
            
            # Extraer datos del mensaje
            session_id = message_json.get("sessionId")
            prompt = message_json.get("prompt")
            
            # Log para ver el mensaje recibido
            print(f"Mensaje recibido: sessionId={session_id}, prompt={prompt}")

            # Preparar el documento para MongoDB
            conversation_data = {
                "conversation_id": session_id,
                "created": datetime.utcnow(),
                "message": [
                    {
                        "content": prompt,
                        "role": "user",
                        "id": message_json.get("messageId", ""),  # ID opcional, si existe en el mensaje
                    }
                ],
                "nameHistory": message_json.get("nameHistory", "default"),
                "testType": message_json.get("testType", "general"),
                "typeContext": message_json.get("typeContext", "defaultContext")
            }
            
            # Guardar en MongoDB
            self.conversations_collection.insert_one(conversation_data)
