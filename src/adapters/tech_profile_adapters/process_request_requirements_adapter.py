
import uuid
import re
import logging
from datetime import datetime
from src.ports.test_cases_ports.process_request_requirements_port import ProcessRequestRequirementsPort
from src.ports.output_ports.mongo_port import MongoDBPort
from src.ports.conversation_ports.name_history_generator_port import NameHistoryGeneratorPort
from src.ports.conversation_ports.conversation_management_port import ConversationManagementPort
from src.ports.output_ports.llm_port import LLMPort
from src.ports.test_cases_ports.count_tokens_port import CountTokensPort
import requests
import os
import json

class ProcessRequestRequirementsAdapter(ProcessRequestRequirementsPort):
    def __init__(self, llm: LLMPort, mongo_repo: MongoDBPort, name_history_generator: 
        NameHistoryGeneratorPort, conversation_manager: ConversationManagementPort, count_tokens: CountTokensPort):
        self.llm = llm
        self.name_history_generator = name_history_generator
        self.count_tokens = count_tokens
        self.mongo_repo = mongo_repo
        self.conversation_manager = conversation_manager
        self.conversation_history = {}
        self.conversation_id = None
        self.logger = logging.getLogger(__name__)
        self.api_extractor_text_url = os.environ.get('API_TEXT_EXTRACT_BASE_URL', 'http://localhost:7000/process-file')
        self.logger.info("ProcessUserStorydapter initialized")

    def _process_request_requirements(self, input_data, conversation_id, user_message, previous_messages):
        """Procesa el testType 'request_requirements'."""
        self.logger.debug("Procesando test_type 'request_requirements'...")
    
        if not self.conversation_id:
            self.conversation_id = input_data['data'].get('conversation_id') or str(uuid.uuid4())
            self.logger.debug(f"Conversation ID asignado: {self.conversation_id}")
        else:
            self.logger.debug(f"Conversation ID ya existente: {self.conversation_id}")
        try:
            existing_conversation = self.mongo_repo.get_conversation_by_id(self.conversation_id)
            existing_messages = existing_conversation.get('data', {}).get('message', [])
            tokens_input_existing = existing_conversation.get('data', {}).get('tokens_input', 0)
            tokens_output_existing = existing_conversation.get('data', {}).get('tokens_output', 0)
        except (ValueError, Exception):
            # Si no existe la conversación, iniciar con lista vacía
            existing_messages = []
            tokens_input_existing = 0
            tokens_output_existing = 0
            self.logger.debug("No se encontró conversación existente. Iniciando nueva.")

        date_created = input_data['data'].get('created') or datetime.utcnow().isoformat()
        messages = input_data['data'].get('message', [])
        name_history = input_data['data'].get('nameHistory')
        step = input_data['data'].get('step')
        select_value = input_data['data'].get('selectValue')
        process_phase = input_data['data'].get('process_phase')
        user_id = input_data['data'].get('userID')
        max_tokens = 3500
        isSelectBlock = input_data['data'].get('isSelectBlock', False)
        if not isinstance(isSelectBlock, bool):
            self.logger.error("El valor de 'isSelectBlock' no es booleano.")
            return {"error": "El valor de 'isSelectBlock' debe ser booleano."}, 400
        
        self.logger.debug(f"conversation_id: {self.conversation_id}, date_created: {date_created}, name_history: {name_history}, user_id: {user_id}")
        
        # Validar que el userID exista
        if not user_id:
            self.logger.error("No se proporcionó un userID válido.")
            return {"error": "Se requiere un userID válido para crear la conversación."}, 400
        
        # Verificar si el userID existe en la base de datos
        try:
            all_users = self.mongo_repo.get_all_users()
            user_exists = any(user['_id'] == user_id for user in all_users)
            if not user_exists:
                self.logger.error(f"El userID {user_id} no existe en la base de datos.")
                return {"error": "El userID proporcionado no existe en la base de datos."}, 404
        except Exception as e:
            self.logger.error(f"Error al verificar el userID en la base de datos: {str(e)}")
            return {"error": "Error al verificar el userID en la base de datos."}, 500

        # Procesar el último mensaje
        request_requirements = None
        message = messages[-1] if messages else None

        if message and message.get('role') == 'user':
            content = message.get('content')

            # Verificar si content es un objeto con file_type (indicando que es un archivo)
            if isinstance(content, dict) and 'file_type' in content:
                try:
                    self.logger.debug(f"Procesando archivo con el microservicio: {content}")
                    response = requests.post(self.api_extractor_text_url, json=content)
                    response.raise_for_status()
                    request_requirements = response.json()

                    # Reemplazar completamente el content con la respuesta del microservicio
                    if request_requirements and isinstance(request_requirements, dict):
                        message['content'] = request_requirements
                        request_requirements = request_requirements.get('source', {}).get('data', "")
                        self.logger.debug(f"Archivo procesado y actualizado: {message['content']}")
                    else:
                        self.logger.error("La respuesta del microservicio no tiene el formato esperado")
                        return {"error": "La respuesta del microservicio no tiene el formato esperado"}, 500
                except requests.exceptions.RequestException as e:
                    self.logger.error(f"Error al llamar al microservicio: {str(e)}")
                    return {"error": f"Error al llamar al microservicio: {str(e)}"}, 500
            else:
                # Si no es un archivo, usar el contenido directamente
                request_requirements = content

        # Validar el request_requirements del usuario
        is_valid_request_requirements = self.validate_request_requirements(request_requirements or user_message)
        self.logger.debug(f"Validez del request_requirements: {is_valid_request_requirements}")
        
        # Si el request_requirements es válido y no hay un nombre de historia, generarlo
        if is_valid_request_requirements and not name_history:
            name_history = self.name_history_generator.generate_name_history(request_requirements or user_message)
            self.logger.debug(f"Nombre de historia generado: {name_history}")
        else:
            # Si el request_requirements no es válido, usar las primeras palabras del mensaje como nombre de la historia
            name_history = name_history or ' '.join((request_requirements or user_message).strip().split()[:5]) 
            self.logger.debug(f"Nombre de historia generado sin IA: {name_history}")

        if is_valid_request_requirements:
            try:
                # Extract capabilities from the validated requirements
                capabilities = self.extract_capabilities(request_requirements or user_message)
                
                # Save the extracted capabilities
                self.mongo_repo.save_capability(capabilities)
                
                self.logger.info(f"Capabilities extracted and saved: {capabilities}")
            except Exception as e:
                self.logger.error(f"Error in extracting or saving capabilities: {str(e)}")
                
        # Crear nuevos mensajes
        new_messages = []
        try:
            new_messages = [
                {
                    "id": str(uuid.uuid4()),
                    "role": msg['role'],
                    "content": msg['content']
                } for msg in messages if 'role' in msg and 'content' in msg
            ]
            self.logger.debug(f"Nuevos mensajes creados: {new_messages}")
        except Exception as e:
            self.logger.error(f"Error al crear nuevos mensajes: {str(e)}")
            return {"error": f"Error al crear nuevos mensajes: {str(e)}"}, 500

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

        # Formatear el contenido después de contar los tokens
        for message in new_messages:
            if message.get('role') == 'user':
                content = message.get('content')
                if isinstance(content, dict) and 'source' in content:
                    # Crear un nuevo diccionario con los campos deseados
                    formatted_content = {
                        "file_name": content.get('file_name', ''),
                        "file_size": content.get('file_size', 0),
                        "file_type": content.get('file_type', ''),
                        "file_url": content.get('file_url', ''),
                        "status": content.get('source', {}).get('status', 'unknown')
                    }
                    
                    message['content'] = formatted_content
                    
                    self.logger.debug(f"Contenido de mensaje formateado: {message['content']}")
                
        # Generar el mensaje de validación del request_requirements según el tipo de prueba
        if process_phase == "request_requirements":
            validation_message = {
                "id": str(uuid.uuid4()),
                "role": "assistant",
                "content": (
                    "¡Gracias por proporcionar los requerimientos técnicos! Ahora necesito que incluyas una lista de habilidades, tecnologías y conocimientos específicos que el candidato debe poseer para este puesto de trabajo."
                    if is_valid_request_requirements
                    else (
                        "Parece que los requerimientos técnicos proporcionados no son claros o están incompletos. "
                        "Por favor, asegúrate de incluir información relevante como habilidades necesarias, experiencia requerida, tecnologías específicas o certificaciones relacionadas con el puesto. "
                        "Esto me ayudará a entender mejor lo que necesitas."
                    )
                ),
                "validate": is_valid_request_requirements
            }
        else:
            # Mensaje genérico para tipos desconocidos
            validation_message = {
                "id": str(uuid.uuid4()),
                "role": "system",
                "content": (
                    "El tipo de requerimiento especificado no es reconocido. Por favor, verifica el valor proporcionado en 'requestType'."
                ),
                "validate": False
            }

        # Apilar las conversaciones nuevas con los mensajes de validación
        updated_messages = new_messages + [validation_message]
        self.logger.debug(f"Conversaciones actualizadas: {updated_messages}")

        # Calcular tokens de salida y total
        try:
            tokens_output = sum(
                self.count_tokens.count_tokens(msg['content'])
                for msg in updated_messages
                if msg['role'] == 'assistant'
            )
            validation_tokens = self.count_tokens.count_tokens(validation_message['content'])
            tokens_output += validation_tokens
            
        except Exception as e:
            self.logger.error(f"Error al contar los tokens de salida: {str(e)}")
            return {"error": f"Error al contar los tokens de salida: {str(e)}"}, 500
            
        # Combinar mensajes existentes con nuevos mensajes
        combined_messages = existing_messages + new_messages
        combined_messages.append(validation_message)
        
        tokens_input += tokens_input_existing 
        tokens_output += tokens_output_existing
        
        total_tokens = tokens_input + tokens_output
        
        # Construir la respuesta
        response_data = {
            "_id": self.conversation_id,
            "created": date_created,
            "conversation_id": self.conversation_id,
            "nameHistory": name_history,
            "userID": user_id,
            'step': step,
            "isSelectBlock": isSelectBlock,
            "selectValue": select_value,
            "process_phase": process_phase,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "tokens": total_tokens,
            "max_tokens": max_tokens,
            "message": [validation_message]
        }
        
        message_to_save = {
            "_id": self.conversation_id,
            "data": {
                "conversationId": self.conversation_id,
                "nameHistory": name_history,
                "userID": user_id,
                "step": step,
                "isSelectBlock": isSelectBlock,
                "selectValue": select_value,
                "process_phase": process_phase,
                "tokens_input": tokens_input,
                "tokens_output": tokens_output,
                "tokens": total_tokens,
                "max_tokens": max_tokens,
                "message": [
                    msg for msg in combined_messages 
                    if msg['role'] in ["user", "assistant", "system"]
                ]
            }
        }
        # Guardar en MongoDB
        self.mongo_repo.save_conversation(message_to_save)
        self.logger.info("conversaciones guardados en MongoDB.")
        
        # Guardar la conversación en la historia
        self.conversation_history[self.conversation_id] = combined_messages
        self.conversation_manager.save_conversation(self.conversation_id, user_message, name_history, is_valid_request_requirements)

        self.logger.info("Conversación guardada exitosamente.")

        return {"data": response_data}, 200

    def validate_request_requirements(self, request_requirements: str) -> bool:
        self.logger.debug(f"Validando request_requirements: {request_requirements}")
        
        # Generar el prompt de validación
        validation_prompt = self.prompt_validation_request_requirements(request_requirements)
        self.logger.debug(f"Prompt de validación generado: {validation_prompt}")
        
        # Llamar a la generación de respuesta
        response_tuple = self.llm.generate_response(validation_prompt)
        
        # Asegurarse de que la respuesta sea una tupla y tenga contenido
        if isinstance(response_tuple, tuple) and len(response_tuple) > 0:
            response = response_tuple[0]
        else:
            response = str(response_tuple)

        self.logger.debug(f"Respuesta del LLM antes de limpieza: '{response}'")
        
        cleaned_response = re.sub(r'[^a-zA-Z]', '', response.strip().lower())
        
        # Depuración: Mostrar la respuesta limpia
        self.logger.debug(f"Respuesta limpia: '{cleaned_response}'")

        if cleaned_response == 'true':
            self.logger.debug("Validación exitosa: La respuesta es 'True'.")
            return True
        elif cleaned_response == 'false':
            self.logger.debug("Validación fallida: La respuesta es 'False'.")
            return False
        else:

            self.logger.warning(f"Respuesta inesperada: {cleaned_response}. Esperado 'True' o 'False'.")
            return False

    def prompt_validation_request_requirements(self, request_requirements: str) -> str:
        return f"""
        Responde solo con "True" o "False".
        Instrucciones:
        Evalúa los requerimientos técnicos proporcionados y determina si están relacionados con un puesto laboral, cumpliendo con los siguientes criterios. Responde únicamente con "True" o "False".

        Criterios de evaluación:
        Claridad: ¿Son claros y comprensibles?
        Especificidad: ¿Incluyen detalles relevantes como habilidades, experiencia, tecnologías o certificaciones específicas?
        Relevancia: ¿Están alineados con las expectativas de un puesto laboral técnico?
        Detalla el nivel y si es indispensable o deseable.
        Requerimientos técnicos actuales:
        {request_requirements}
        
        No incluyas comentarios adicionales, solo responde con "True" o "False".
        """
    
    def prompt_extract_capabilities(self, request_requirements: str) -> str:
        return f"""
        INSTRUCCIONES ABSOLUTAMENTE ESTRICTAS:
        - Extrae las capacidades.
        - Devuelve las capacidades técnicas como un texto, separadas por comas.
        - NO incluyas explicaciones adicionales.

        Texto a analizar:
        {request_requirements}
        """

    def extract_capabilities(self, request_requirements: str) -> dict:
        self.logger.debug(f"Inicio de extracción de capacidades. Texto de requerimiento: '{request_requirements}'")
        
        # Generar el prompt de extracción
        capacibilitie_id = str(uuid.uuid4()) 
        extraction_prompt = self.prompt_extract_capabilities(request_requirements)
        self.logger.debug(f"Prompt de extracción generado: {extraction_prompt}")
        
        try:
            
            self.logger.debug("Llamando al modelo LLM con el prompt...")
            response_tuple = self.llm.generate_response(extraction_prompt)
            
            # Verificación detallada de la respuesta
            if not response_tuple:
                self.logger.error("La respuesta del modelo es nula o vacía (response_tuple vacío).")
                raise ValueError("La respuesta del modelo no es válida o está vacía.")
            
            self.logger.debug(f"Respuesta obtenida del modelo: {response_tuple}")
            
            response = response_tuple 
            
            capacibilities = response  
            
            self.logger.debug(f"Habilidades técnicas extraídas: {capacibilities}")
        
        except Exception as e:
            self.logger.error(f"Error general al procesar la respuesta: {e}", exc_info=True)
            capacibilities = ""

        result = {
            "_id": capacibilitie_id,
            "conversation_id": self.conversation_id,
            "capacibilitie_id": capacibilitie_id,
            "requirement_text": request_requirements,
            "Capacidades": capacibilities,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        self.logger.debug(f"Estructura final generada: {result}")
        return result