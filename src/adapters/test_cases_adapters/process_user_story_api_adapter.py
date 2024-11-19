import uuid
import datetime
import logging

from src.ports.test_cases_ports.process_user_story_api_port import ProcessUserStoryAPIPort
from src.ports.output_ports.llm_port import LLMPort
from src.ports.output_ports.mongo_port import MongoDBPort
from src.ports.test_cases_ports.count_tokens_port import CountTokensPort
from src.ports.test_cases_ports.test_case_prompt_generator_port import TestCasePromptGeneratorPort
from src.ports.conversation_ports.conversation_management_port import ConversationManagementPort

class ProcessUserStoryApiAdapter(ProcessUserStoryAPIPort):
    def __init__(self, llm: LLMPort, mongo_repo: MongoDBPort ,
                prompt_generator_api: TestCasePromptGeneratorPort,conversation_manager: 
                    ConversationManagementPort, count_tokens: CountTokensPort):
        self.llm = llm
        self.mongo_repo = mongo_repo
        self.conversation_manager = conversation_manager
        self.prompt_generator_api = prompt_generator_api
        self.count_tokens = count_tokens
        self.conversation_history = {}
        self.logger = logging.getLogger(__name__)
        self.logger.info("ProcessUserStoryApiAdapter initialized")

    def _process_user_story(self, input_data) -> dict:
        """Procesa una historia de usuario y genera casos de prueba."""
        self.logger.info(f"Procesando historia de usuario con input_data: {input_data}")
        
        # Extraer datos necesarios del input
        conversation_id = input_data['data'].get('conversation_id')
        date_created = input_data['data'].get('created')
        messages = input_data['data'].get('message', [])
        name_history = input_data['data'].get('nameHistory')
        step = input_data['data'].get('step')
        user_id = input_data['data'].get('userID')
        select_value = input_data['data'].get('selectValue')
        testType = input_data['data'].get('testType')
        typeContext = input_data['data'].get('typeContext')
        context_level = input_data['data'].get('contextLevel')
        isSelectBlock = input_data['data'].get('isSelectBlock', False)
        if not isinstance(isSelectBlock, bool):
            self.logger.error("El valor de 'isSelectBlock' no es booleano.")
            return {"error": "El valor de 'isSelectBlock' debe ser booleano."}, 400
        max_tokens = 3500
        
        # Obtener el último mensaje con validate=True, excluyendo el último mensaje
        context_business = ""
        for msg in reversed(messages[:-1]):  # Excluimos el último mensaje
            if msg.get('validate') is True:
                context_business = msg['content']
                break
            
        # Si no se encontró ningún mensaje con validate=True
        if not context_business:
            self.logger.warning("No se encontró ningún mensaje previo con validate=True")
            context_business = ""
        
        # Determinar el contexto según el tipo de `content`count_tokens
        if isinstance(messages[-2]['content'], str):
            context_technical = messages[-2]['content']
        elif isinstance(messages[-2]['content'], list):
            # Extraer el campo "data" si `content` es una lista con estructura específica
            context_technical = messages[-2]['content'][0].get("source", {}).get("data", "")
        else:
            context_technical = "" 
        
        # Obtener la última conversación (historia de usuario)
        user_story = messages[-1]['content'] if messages else ""
        
        # Validar la historia de usuario
        is_valid_user_story = self.validate_user_story(user_story)
        self.logger.debug(f"Validez de la historia de usuario: {is_valid_user_story}")

        # Crear nuevas conversaciones preservando los campos validate existentes
        new_messages = []
        for msg in messages:
            new_msg = {
                "id": str(uuid.uuid4()),
                "role": msg['role'],
                "content": msg['content']
            }
            # Preservar el campo validate si existe en el mensaje original
            if 'validate' in msg:
                new_msg['validate'] = msg['validate']
            new_messages.append(new_msg)
        self.logger.debug(f"Nuevas conversaciones creadas: {new_messages}")
        
        # Inicializar contadores de tokens
        tokens_input = 0
        tokens_output = 0

        try:
            # Calcular tokens de entrada (mensajes del usuario)
            for message in new_messages:
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

            # Calcular tokens de salida (mensajes del asistente)
            for message in new_messages:
                if message.get('role') == 'assistant':
                    content = message.get('content')
                    if isinstance(content, str):
                        tokens_output += self.count_tokens.count_tokens(content)
                    # Si el contenido es otro tipo de dato (como un archivo), podrías manejarlo de forma similar si lo necesitas

            self.logger.debug(f"Tokens de salida: {tokens_output}")

        except Exception as e:
            self.logger.error(f"Error al contar los tokens: {str(e)}")
            return {"error": f"Error al contar los tokens: {str(e)}"}, 500

        # Calcular el total de tokens
        total_tokens = tokens_input + tokens_output
        self.logger.debug(f"Total de tokens: {total_tokens}")

        # Crear conversaciones de validación
        validation_messages = []
        
        # Obtener los mensajes validados previos
        previous_validated_messages = [
            msg for msg in new_messages[:-1]  # Excluir el último mensaje
            if 'validate' in msg
        ]
        
        # Obtener los IDs de los mensajes validados previos
        previous_validated_ids = [msg['id'] for msg in previous_validated_messages]
        
        # Añadir validated_message_ids solo al último mensaje de new_messages si tiene validate
        if new_messages and 'validate' in new_messages[-1]:
            new_messages[-1]['validated_message_ids'] = previous_validated_ids

        
        # Crear conversaciones de validación para el nuevo mensaje
        if is_valid_user_story:
            test_cases = self.prompt_generator_api.promt_generate_test_cases(context_business, context_technical, user_story)
            validation_messages = [
                {
                    "id": str(uuid.uuid4()),
                    "role": "assistant",
                    "content": (
                        f"¡Gracias por la información! A continuación, te presento el caso de prueba generado basado en la Historia de Usuario proporcionada: {test_cases}"
                    ),
                    "validate": True
                }
            ]
        else:
            validation_messages = [
                {
                    "id": str(uuid.uuid4()),
                    "role": "assistant",
                    "content": (
                        "¡Gracias por tu respuesta! Sin embargo, la información proporcionada no parece seguir el formato de una Historia de Usuario. "
                        "Para crear un caso de prueba adecuado, la historia de usuario debe ser clara, concisa y describir lo que un usuario necesita hacer.\n\n"
                        
                        "Asegúrate de que incluya:\n"
                        "  - Un rol claro (quién está solicitando la historia).\n"
                        "  - Una acción específica (qué quiere hacer el usuario).\n"
                        "  - Un resultado deseado (por qué es importante).\n\n"

                        "Por ejemplo, una HU válida sería: \"Como gerente de ventas, quiero enviar el reporte de ventas por correo "
                        "para que el equipo de ventas tenga acceso a información actualizada y pueda tomar decisiones informadas.\""
                    ),
                    "validate": False
                }
            ]

        # Combinar todas las conversaciones
        updated_messages = new_messages + validation_messages
        self.logger.debug(f"Conversaciones actualizadas: {updated_messages}")

        # Actualizar tokens de salida y total incluyendo el mensaje de validación
        validation_tokens = sum(self.count_tokens.count_tokens(msg['content']) for msg in validation_messages)
        tokens_output += validation_tokens
        total_tokens += validation_tokens

        # Construir la respuesta
        response_data = {
            "_id": conversation_id,
            "created": date_created,
            "conversation_id": conversation_id,
            "nameHistory": name_history,
            "userId": user_id,
            "step": step,
            "isSelectBlock": isSelectBlock,
            "selectValue": select_value,
            "typeContext": typeContext,
            "testType": testType,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "tokens": total_tokens,
            "max_tokens": max_tokens,
            "message": updated_messages
        }
        
        # Actualizar los campos que deseas, excluyendo nameHistory
        update_fields = {
            "data.typeContext": typeContext,
            "data.testType": testType,
            "data.step": step,
            "data.contextLevel": context_level,
            "data.isSelectBlock": isSelectBlock,
            "data.selectValue": select_value,
            "data.tokens_input": tokens_input,
            "data.tokens_output": tokens_output,
            "data.tokens": total_tokens,
            "data.message": [
                msg for msg in updated_messages 
                if msg['role'] in ["user", "assistant", "system"]
            ]
        }
        self.mongo_repo.update_conversation_user_story(conversation_id, update_fields)
        
        # Guardar en el historial de conversaciones
        self.conversation_history[conversation_id] = updated_messages
        self.conversation_manager.save_conversation(conversation_id, user_story, name_history, is_valid_user_story)
        
        self.logger.info("Procesamiento de historia de usuario completado exitosamente.")
        
        return {"data": response_data}, 200

    def validate_user_story(self, user_story: str) -> bool:
        self.logger.debug(f"Validando historia de usuario: {user_story}")
        
        # Generar el prompt para la validación
        validation_prompt = self.prompt_validation_user_story(user_story)
        self.logger.debug(f"Prompt de validación de historia de usuario: {validation_prompt}")
        
        # Llamar al LLM para obtener la respuesta
        response = self.llm.generate_response(validation_prompt)

        # Manejo de la respuesta para asegurar que sea una cadena
        if isinstance(response, tuple):
            response = response[0]

        self.logger.debug(f"Respuesta de validación de historia de usuario: {response}")

        # Comprobar la respuesta de manera robusta
        response_str = response.strip().lower()
        if response_str in ['true', 'yes', 'valid']:
            return True
        elif response_str in ['false', 'no', 'invalid']:
            return False

        self.logger.error("Respuesta inesperada del modelo: %s", response)
        return False  # O lanza una excepción si prefieres

    def prompt_validation_user_story(self, user_story: str) -> str:
        return f"""
        La historia de usuario debe ser clara, concisa y describir lo que un usuario necesita hacer. 
        Asegúrate de que incluya:
        - Un rol claro (quién está solicitando la historia).
        - Una acción específica (qué quiere hacer el usuario).
        - Un resultado deseado (por qué es importante).

        Historia de usuario actual: {user_story}

        ¿Esta historia de usuario cumple con los criterios mencionados?
        Responde únicamente con 'true' si cumple o 'false' si no cumple, sin ninguna explicación adicional.
        """