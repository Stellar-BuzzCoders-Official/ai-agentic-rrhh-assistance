# src/adapters/context_validation_adapter.py
import uuid
import logging
from datetime import datetime
from src.ports.test_cases_ports.process_context_api_port import ProcessContextApiPort
from src.ports.output_ports.mongo_port import MongoDBPort
from src.ports.conversation_ports.name_history_generator_port import NameHistoryGeneratorPort
from src.ports.conversation_ports.conversation_management_port import ConversationManagementPort
from src.ports.output_ports.llm_port import LLMPort
from src.ports.test_cases_ports.count_tokens_port import CountTokensPort
import base64
import requests
from dotenv import load_dotenv
import os

# Configuración del logger
logging.basicConfig(level=logging.DEBUG)

class ProcessContextApiAdapter(ProcessContextApiPort):
    def __init__(self, llm: LLMPort, mongo_repo: MongoDBPort, name_history_generator: NameHistoryGeneratorPort, conversation_manager: ConversationManagementPort, count_tokens: CountTokensPort):
        self.llm = llm
        self.name_history_generator = name_history_generator
        self.count_tokens = count_tokens
        self.mongo_repo = mongo_repo
        self.conversation_manager = conversation_manager
        self.conversation_history = {}
        self.logger = logging.getLogger(__name__)
        self.api_text_storage_url = os.environ.get('API_TEXT_STORAGE_URL', 'http://qava-cn-ai-storage-text-extraction:7000/process-file')
        self.logger.info(f"Conexion establecida a: {self.api_text_storage_url}")
        
    def _process_context(self, input_data, conversation_id, user_message, previous_messages):
        """Procesa el testType 'context'."""
        
        self.logger.debug("Procesando test_type 'context'...")  

        # Extraer datos necesarios del input
        conversation_id = input_data['data'].get('conversation_id') or str(uuid.uuid4())
        date_created = input_data['data'].get('created') or datetime.utcnow().isoformat()
        messages = input_data['data'].get('message', [])
        name_history = input_data['data'].get('nameHistory')
        step = input_data['data'].get('step')
        select_value = input_data['data'].get('selectValue')
        testType = input_data['data'].get('testType')
        typeContext = input_data['data'].get('typeContext')
        user_id = input_data['data'].get('userID')
        isSelectBlock = input_data['data'].get('isSelectBlock', False)
        context_level = input_data['data'].get('contextLevel')
        
        validated_messages = [msg for msg in messages if 'validate' in msg]
        
        if not isinstance(isSelectBlock, bool):
            self.logger.error("El valor de 'isSelectBlock' no es booleano.")
            return {"error": "El valor de 'isSelectBlock' debe ser booleano."}, 400
        max_tokens = 3500
        
        self.logger.debug(f"conversation_id: {conversation_id}, date_created: {date_created}, name_history: {name_history}, user_id: {user_id}")

        # Validar que el userID exista
        if not user_id:
            self.logger.error("No se proporcionó un userID válido.")
            return {"error": "Se requiere un userID válido para crear la conversación."}, 400

        # Verificar si el userID existe en la base de datos
        try:
            self.logger.debug("Verificando existencia del userID en la base de datos...")
            all_users = self.mongo_repo.get_all_users()
            user_exists = any(user['_id'] == user_id for user in all_users)
            if not user_exists:
                self.logger.error(f"El userID {user_id} no existe en la base de datos.")
                return {"error": "El userID proporcionado no existe en la base de datos."}, 404
            self.logger.debug(f"El userID {user_id} existe en la base de datos.")
        except Exception as e:
            self.logger.error(f"Error al verificar el userID en la base de datos: {str(e)}")
            return {"error": "Error al verificar el userID en la base de datos."}, 500

        # Inicializar processed_content
        processed_content = None

        # Obtener el penúltimo mensaje de usuario
        message = messages[-1] if messages else None

        if message and message.get('role') == 'user':
            content = message.get('content')

            # Verificar si content es un objeto con file_type (indicando que es un archivo)
            if isinstance(content, dict) and 'file_type' in content:
                try:
                    self.logger.debug(f"Procesando archivo con el microservicio: {content}")
                    response = requests.post(self.api_text_storage_url, json=content)
                    response.raise_for_status()
                    processed_data = response.json()

                    # Reemplazar completamente el content con la respuesta del microservicio
                    if processed_data and isinstance(processed_data, dict):
                        message['content'] = processed_data
                        processed_content = processed_data.get('source', {}).get('data', "")
                        self.logger.debug(f"Archivo procesado y actualizado: {message['content']}")
                    else:
                        self.logger.error("La respuesta del microservicio no tiene el formato esperado")
                        return {"error": "La respuesta del microservicio no tiene el formato esperado"}, 500
                except requests.exceptions.RequestException as e:
                    self.logger.error(f"Error al llamar al microservicio: {str(e)}")
                    return {"error": f"Error al llamar al microservicio: {str(e)}"}, 500
            else:
                # Si no es un archivo, usar el contenido directamente
                processed_content = content

        # Validar el contexto del usuario con el contenido procesado
        try:
            is_valid_context = self.validate_context(processed_content)
            self.logger.debug(f"Validez del contexto: {is_valid_context}")
        except Exception as e:
            self.logger.error(f"Error al validar el contexto: {str(e)}")
            return {"error": f"Error al validar el contexto: {str(e)}"}, 500

        # Si el contexto es válido y no hay un nombre de historia, generarlo
        if is_valid_context and not name_history:
            try:
                name_history = self.name_history_generator.generate_name_history(processed_content)
                self.logger.debug(f"Nombre de historia generado: {name_history}")
            except Exception as e:
                self.logger.error(f"Error al generar el nombre de historia: {str(e)}")
                return {"error": f"Error al generar el nombre de historia: {str(e)}"}, 500
        else:
            # Si el contexto no es válido, usar las primeras palabras del mensaje como nombre de la historia
            name_history = name_history or ' '.join(processed_content.strip().split()[:5])
            self.logger.debug(f"Nombre de historia generado sin IA: {name_history}")

        # Crear nuevos mensajes de conversación
        new_messages = []
        try:
            new_messages = [
                {
                    "id": str(uuid.uuid4()),
                    "role": msg['role'],
                    "content": msg['content'],
                    **({"validate": msg['validate']} if 'validate' in msg else {})
                } for msg in messages if 'role' in msg and 'content' in msg
            ]
            self.logger.debug(f"Nuevos mensajes creados: {new_messages}")
        except Exception as e:
            self.logger.error(f"Error al crear nuevos mensajes: {str(e)}")
            return {"error": f"Error al crear nuevos mensajes: {str(e)}"}, 500
        
        # Obtener solo los mensajes validados previos
        previous_validated_messages = [
            msg for msg in new_messages[:-1]  # Excluir el último mensaje
            if 'validate' in msg
        ]
        
        # Obtener los IDs de los mensajes validados previos
        previous_validated_ids = [msg['id'] for msg in previous_validated_messages]
        
        # Añadir validated_message_ids solo al último mensaje de new_messages si tiene validate
        if new_messages and 'validate' in new_messages[-1]:
            new_messages[-1]['validated_message_ids'] = previous_validated_ids
        
        # Crear el mensaje de validación (sin validated_message_ids)
        validation_message = {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": (
                "¡Gracias por el contexto! Ahora necesito que me proporciones la Historia de Usuario (HU) para poder generar los casos de prueba."
                if is_valid_context
                else (
                    "Parece que el contexto proporcionado no está suficientemente claro para la generación de casos de prueba para APIs. "
                    "Para ayudarte mejor, el contexto debe incluir detalles técnicos específicos sobre la API, como su funcionalidad, los endpoints disponibles, "
                    "los parámetros requeridos y las respuestas esperadas. Asegúrate también de que el contexto describa las interacciones esperadas y cualquier "
                    "restricción técnica relevante. Esto facilitará la creación de casos de prueba precisos."
                )
            ),
            "validate": is_valid_context
        }
        
        # Apilar las conversaciones actualizadas
        updated_messages = new_messages + [validation_message]
        self.logger.debug(f"Conversaciones actualizadas: {updated_messages}")

        # Contar los tokens dependiendo del tipo de contenido
        tokens_input = 0
        try:
            for message in messages:
                if message.get('role') == 'user':
                    content = message.get('content')
                    if isinstance(content, dict):
                        # Si es un diccionario (caso de archivo), obtener el campo 'data'
                        if 'source' in content and 'data' in content['source']:
                            tokens_input += self.count_tokens.count_tokens(content['source']['data'])
                        elif 'data' in content:
                            tokens_input += self.count_tokens.count_tokens(content['data'])
                    elif isinstance(content, list):
                        # Si es una lista de archivos, procesar cada uno
                        for item in content:
                            if isinstance(item, dict) and 'source' in item and 'data' in item['source']:
                                tokens_input += self.count_tokens.count_tokens(item['source']['data'])
                    else:
                        # Si es una cadena, contar los tokens directamente
                        tokens_input += self.count_tokens.count_tokens(str(content))
            self.logger.debug(f"Tokens de entrada: {tokens_input}")
        except Exception as e:
            self.logger.error(f"Error al contar los tokens de entrada: {str(e)}")
            return {"error": f"Error al contar los tokens de entrada: {str(e)}"}, 500

        # Contar los tokens de salida (mensaje de validación)
        try:
            tokens_output = self.count_tokens.count_tokens(validation_message['content'])
            self.logger.debug(f"Tokens de salida (validación): {tokens_output}")
        except Exception as e:
            self.logger.error(f"Error al contar los tokens de salida: {str(e)}")
            return {"error": f"Error al contar los tokens de salida: {str(e)}"}, 500

        # Calcular el total de tokens
        total_tokens = tokens_input + tokens_output
        self.logger.debug(f"Total de tokens: {total_tokens}")

        # Crear la respuesta con los nuevos campos
        response_data = {
            "_id": conversation_id,
            "created": date_created,
            "conversation_id": conversation_id,
            "nameHistory": name_history,
            "userID": user_id,
            'step': step,
            "selectValue": select_value,
            "contextLevel": context_level,
            "isSelectBlock": isSelectBlock,
            "typeContext": typeContext,
            "testType": testType,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "tokens": total_tokens,
            "max_tokens": max_tokens,
            "message": updated_messages
        }

        # Guardar en MongoDB
        message_to_save = {
            "_id": conversation_id,
            "data": {
                "conversationId": conversation_id,
                "nameHistory": name_history,
                "userID": user_id,
                "step": step,
                "selectValue": select_value,
                "typeContext": typeContext,
                "testType": testType,
                "tokens_input": tokens_input,
                "tokens_output": tokens_output,
                "tokens": total_tokens,
                "max_tokens": max_tokens,
                "message": updated_messages
            }
        }
        
        try:
            self.mongo_repo.save_conversation(message_to_save)
            self.logger.info("Conversaciones guardadas en MongoDB.")
        except Exception as e:
            self.logger.error(f"Error al guardar la conversación en MongoDB: {str(e)}")
            return {"error": f"Error al guardar la conversación en MongoDB: {str(e)}"}, 500

        self.conversation_history[conversation_id] = updated_messages
        self.conversation_manager.save_conversation(conversation_id, processed_content, name_history, is_valid_context)

        self.logger.info("Conversación guardada exitosamente.")

        return {"data": response_data}, 200

    def validate_context(self, context: str) -> bool:
        self.logger.debug(f"Validando contexto: {context}")
        validation_prompt = self.prompt_validation_context(context)
        self.logger.debug(f"Prompt de validación generado: {validation_prompt}")

        response_tuple = self.llm.generate_response(validation_prompt)
        
        # Asegúrate de que response_tuple sea un tipo esperado
        if isinstance(response_tuple, tuple) and len(response_tuple) > 0:
            response = response_tuple[0]
        else:
            response = str(response_tuple)

        self.logger.debug(f"Respuesta del LLM: {response}")

        # Normaliza la respuesta
        response_normalized = response.strip().lower()

        # Verifica la respuesta
        if response_normalized == 'true':
            return True
        elif response_normalized == 'false':
            return False
        else:
            self.logger.warning(f"Respuesta inesperada del LLM: {response_normalized}")
            return False

    def prompt_validation_context(self, context: str) -> str:
        return f"""
        Acepta como contexto técnico un documento en formato Swagger, GraphQL (en estructura JSON) u OpenAPI, y también texto que describa una API. Responde únicamente con 'true' o 'false':

        ¿El siguiente texto representa código de un Swagger, GraphQL en JSON, OpenAPI, o al menos una descripción textual de una API?
        
        {context}"""