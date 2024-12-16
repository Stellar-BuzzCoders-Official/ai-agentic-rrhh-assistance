
import uuid
import datetime
import logging
from src.ports.test_cases_ports.process_request_cv_port import ProcessRequestCvPort
from src.ports.output_ports.llm_port import LLMPort
from src.ports.output_ports.mongo_port import MongoDBPort
from src.ports.test_cases_ports.test_case_prompt_generator_port import TestCasePromptGeneratorPort
from src.ports.conversation_ports.conversation_management_port import ConversationManagementPort
from src.ports.test_cases_ports.count_tokens_port import CountTokensPort
import requests
import json
import os
import re

class ProcessCvAdapter(ProcessRequestCvPort):
    def __init__(self, llm: LLMPort, mongo_repo: MongoDBPort, 
                prompt_generator: TestCasePromptGeneratorPort, conversation_manager: 
                    ConversationManagementPort, count_tokens: CountTokensPort):
        self.llm = llm
        self.mongo_repo = mongo_repo
        self.conversation_manager = conversation_manager
        self.prompt_generator = prompt_generator
        self.count_tokens = count_tokens
        self.conversation_history = {}
        self.conversation_id = None
        self.logger = logging.getLogger(__name__)
        self.api_extractor_text_url = os.environ.get('API_TEXT_EXTRACT_BASE_URL', 'http://joyit-cn-ai-storage-text-extraction:7000/process-file')

    def _process_request_cv(self, input_data, conversation_id,user_message, previous_messages):
        """Procesa una historia de usuario y genera casos de prueba."""
        self.logger.info(f"Procesando historia de usuario con input_data: {input_data}")
        
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
            
        date_created = input_data['data'].get('created')
        messages = input_data['data'].get('message', [])
        name_history = input_data['data'].get('nameHistory')
        step = input_data['data'].get('step')
        user_id = input_data['data'].get('userID')
        select_value = input_data['data'].get('selectValue')
        process_phase = input_data['data'].get('process_phase')
        typerequest_cv = input_data['data'].get('typerequest_cv')
        isSelectBlock = input_data['data'].get('isSelectBlock', False)
        if not isinstance(isSelectBlock, bool):
            self.logger.error("El valor de 'isSelectBlock' no es booleano.")
            return {"error": "El valor de 'isSelectBlock' debe ser booleano."}, 400
        
        self.logger.debug(f"conversation_id: {self.conversation_id}, date_created: {date_created}, name_history: {name_history}, user_id: {user_id}")
        max_tokens = 3500
        
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
        request_cv = None
        message = messages[-1] if messages else None

        if message and message.get('role') == 'user':
            content = message.get('content')

            # Verificar si content es un objeto con file_type (indicando que es un archivo)
            if isinstance(content, dict) and 'file_type' in content:
                try:
                    self.logger.debug(f"Procesando archivo con el microservicio: {content}")
                    response = requests.post(self.api_extractor_text_url, json=content)
                    response.raise_for_status()
                    request_cv = response.json()

                    # Reemplazar completamente el content con la respuesta del microservicio
                    if request_cv and isinstance(request_cv, dict):
                        message['content'] = request_cv
                        request_cv = request_cv.get('source', {}).get('data', "")
                        self.logger.debug(f"Archivo procesado y actualizado: {message['content']}")
                    else:
                        self.logger.error("La respuesta del microservicio no tiene el formato esperado")
                        return {"error": "La respuesta del microservicio no tiene el formato esperado"}, 500
                except requests.exceptions.RequestException as e:
                    self.logger.error(f"Error al llamar al microservicio: {str(e)}")
                    return {"error": f"Error al llamar al microservicio: {str(e)}"}, 500
            else:
                request_cv = content

        # Validar la historia de usuario
        is_valid_request_cv = self.validate_request_cv(request_cv or user_message)
        self.logger.debug(f"Validez de la historia de usuario: {is_valid_request_cv}")

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

        conversation_id = self.conversation_id # O el ID actual de la conversación
        capabilities = self.mongo_repo.get_capabilities_by_conversation_id(conversation_id)
        self.logger.debug(f"Capacidades recuperadas: {capabilities}")
        
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
                
        if process_phase == "upload_cv_and_match":
            if is_valid_request_cv:
                technical_report = self.prompt_generator.prompt_generate_technical_report(capabilities,request_cv)
                validation_message = {
                    "id": str(uuid.uuid4()),
                    "role": "assistant",
                    "content": (
                        f"¡Gracias por la información! A continuación, te presento el informe técnico en base al CV y los requerimientos técnicos: {technical_report}"
                    ),
                    "validate": True
                }
            else:
                validation_message = {
                    "id": str(uuid.uuid4()),
                    "role": "assistant",
                    "content": (
                        "¡Gracias por tu respuesta! Sin embargo, el CV proporcionado no parece cumplir con el formato esperado. "
                        "Para procesarlo adecuadamente, asegúrate de que incluya información clara y estructurada.\n\n"
                        
                        "Asegúrate de incluir:\n"
                        "  - Datos personales básicos (nombre, contacto, ubicación).\n"
                        "  - Experiencia laboral relevante (puestos, empresas, fechas).\n"
                        "  - Educación (títulos obtenidos, instituciones, años).\n"
                        "  - Habilidades técnicas y certificaciones (lenguajes de programación, herramientas, etc.).\n\n"

                        "Por ejemplo, un CV válido podría incluir: \"Juan Pérez, ingeniero de software con 5 años de experiencia en desarrollo backend utilizando Python y Django, "
                        "certificado en AWS Solutions Architect.\""
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
            "userId": user_id,
            "step": step,
            "isSelectBlock": isSelectBlock,
            "selectValue": select_value,
            "typerequest_cv": typerequest_cv,
            "process_phase": process_phase,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "tokens": total_tokens,
            "max_tokens": max_tokens,
            "message": [validation_message]
        }
        
        # Solo actualizar los campos que deseas, excluyendo nameHistory
        update_fields = {
            "data.process_phase": process_phase,
            "data.step": step,
            "data.isSelectBlock": isSelectBlock,
            "data.selectValue": select_value,
            "data.process_phase": process_phase,
            "data.tokens_input": tokens_input,
            "data.tokens_output": tokens_output,
            "data.tokens": total_tokens,
            "data.message": [
                msg for msg in combined_messages
                if msg['role'] in ["user", "assistant", "system"]
            ]
        }
        self.mongo_repo.update_conversation_cv_and_match(self.conversation_id, update_fields)
        
        # Guardar en el historial de conversaciones
        self.conversation_history[self.conversation_id] = combined_messages
        self.conversation_manager.save_conversation(self.conversation_id, request_cv, name_history, is_valid_request_cv)
        
        self.logger.info("Procesamiento de historia de usuario completado exitosamente.")
        
        return {"data": response_data}, 200

    def validate_request_cv(self, request_cv: str) -> bool:
        self.logger.debug(f"Validando historia de usuario: {request_cv}")
        
        # Generar el prompt para la validación
        validation_prompt = self.prompt_validation_request_cv(request_cv)
        self.logger.debug(f"Prompt de validación de historia de usuario: {validation_prompt}")
        
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

    def prompt_validation_request_cv(self, request_cv: str) -> str:
        return f"""
        El CV debe ser claro, estructurado y contener información relevante para evaluar al candidato. 
        Asegúrate de que incluya:
        - Datos personales básicos (nombre, contacto, ubicación).
        - Experiencia laboral relevante (puestos, empresas, fechas).
        - Educación (títulos obtenidos, instituciones, años).
        - Habilidades técnicas y certificaciones (lenguajes de programación, herramientas, etc.).

        CV actual: {request_cv}

        ¿Este CV cumple con los criterios mencionados?
        Responde únicamente con 'true' si cumple o 'false' si no cumple, sin ninguna explicación adicional.
        """