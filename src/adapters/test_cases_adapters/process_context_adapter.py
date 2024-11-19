
import uuid
import logging
from datetime import datetime
from src.ports.test_cases_ports.process_context_port import ProcessContextPort
from src.ports.output_ports.mongo_port import MongoDBPort
from src.ports.conversation_ports.name_history_generator_port import NameHistoryGeneratorPort
from src.ports.conversation_ports.conversation_management_port import ConversationManagementPort
from src.ports.output_ports.llm_port import LLMPort
from src.ports.test_cases_ports.count_tokens_port import CountTokensPort

class ProcessContextAdapter(ProcessContextPort):
    def __init__(self, llm: LLMPort, mongo_repo: MongoDBPort, name_history_generator: 
        NameHistoryGeneratorPort, conversation_manager: ConversationManagementPort, count_tokens: CountTokensPort):
        self.llm = llm
        self.name_history_generator = name_history_generator
        self.count_tokens = count_tokens
        self.mongo_repo = mongo_repo
        self.conversation_manager = conversation_manager
        self.conversation_history = {}
        self.logger = logging.getLogger(__name__)
        self.logger.info("ProcessUserStorydapter initialized")

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
        context_level = input_data['data'].get('contextLevel')
        max_tokens = 3500
        isSelectBlock = input_data['data'].get('isSelectBlock', False)
        if not isinstance(isSelectBlock, bool):
            self.logger.error("El valor de 'isSelectBlock' no es booleano.")
            return {"error": "El valor de 'isSelectBlock' debe ser booleano."}, 400
        
        self.logger.debug(f"conversation_id: {conversation_id}, date_created: {date_created}, name_history: {name_history}, user_id: {user_id}")
        
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

        # Validar el contexto del usuario
        is_valid_context = self.validate_context(user_message)
        self.logger.debug(f"Validez del contexto: {is_valid_context}")

        # Si el contexto es válido y no hay un nombre de historia, generarlo
        if is_valid_context and not name_history:
            name_history = self.name_history_generator.generate_name_history(user_message)
            self.logger.debug(f"Nombre de historia generado: {name_history}")
        else:
            # Si el contexto no es válido, usar las primeras palabras del mensaje como nombre de la historia
            name_history = name_history or ' '.join(user_message.strip().split()[:5]) 
            self.logger.debug(f"Nombre de historia generado sin IA: {name_history}")

        # Crear nuevos conversaciones basados en el input
        new_messages = [
            {
                "id": str(uuid.uuid4()),
                "role": msg['role'],
                "content": msg['content']
            } for msg in messages if 'role' in msg and 'content' in msg
        ]
        self.logger.debug(f"Nuevos conversaciones creados: {new_messages}")
        
        # Calcular tokens de entrada (user), salida (assistant) y total
        tokens_input = sum(
            self.count_tokens.count_tokens(msg['content'])
            for msg in new_messages
            if msg['role'] == 'user'
        )
        tokens_output = sum(
            self.count_tokens.count_tokens(msg['content'])
            for msg in new_messages
            if msg['role'] == 'assistant'
        )
        total_tokens = tokens_input + tokens_output
        self.logger.debug(f"Tokens de entrada: {tokens_input}, Tokens de salida: {tokens_output}, Total tokens: {total_tokens}")

        # Generar el mensaje de validación del contexto según el tipo de prueba
        if typeContext == "GenerateTestFunctional":
            validation_message = {
                "id": str(uuid.uuid4()),
                "role": "assistant",
                "content": (
                    "¡Gracias por el contexto! Ahora necesito que me proporciones la Historia de Usuario (HU) para poder generar los casos de prueba."
                    if is_valid_context
                    else (
                        "Parece que el contexto proporcionado no está relacionado con la creación de un caso de prueba. "
                        "Para ayudarte mejor, el contexto proporcionado debe estar relacionado con un negocio, empresa o plan de trabajo. "
                        "Asegúrate de que el contexto sea claro, específico y relevante para un entorno empresarial."
                    )
                ),
                "validate": is_valid_context
            }
        elif typeContext == "GenerateTestFunctionalApi":
            validation_message = {
                "id": str(uuid.uuid4()),
                "role": "system" if is_valid_context else "assistant",
                "content": (
                    "¡Gracias por el contexto! Ahora necesito que me proporciones detalles técnicos de la API, como los endpoints, parámetros requeridos, "
                    "códigos de estado y ejemplos de respuesta, para poder generar los casos de prueba."
                    if is_valid_context
                    else (
                        "El contexto proporcionado no está claro para la generación de casos de prueba para APIs. "
                        "Por favor, proporciona un contexto técnico que describa la funcionalidad de la API, cómo interactúa con otros sistemas, "
                        "y cualquier requisito específico necesario para probarla. Asegúrate de que sea claro y relevante."
                    )
                ),
                "validate": is_valid_context
            }
            
        else:
            # Mensaje genérico para tipos desconocidos
            validation_message = {
                "id": str(uuid.uuid4()),
                "role": "system",
                "content": (
                    "El tipo de prueba especificado no es reconocido. Por favor, verifica el valor proporcionado en 'testType'."
                ),
                "validate": False
            }
        # Apilar los conversaciones nuevos con los conversaciones de validación
        updated_messages = new_messages + [validation_message]
        self.logger.debug(f"conversaciones actualizados: {updated_messages}")
        
        # Actualizar tokens de salida y total incluyendo el mensaje de validación
        validation_tokens = self.count_tokens.count_tokens(validation_message['content'])
        tokens_output += validation_tokens
        total_tokens += validation_tokens
        
        # Construir la respuesta
        response_data = {
            "_id": conversation_id,
            "created": date_created,
            "conversation_id": conversation_id,
            "nameHistory": name_history,
            "userID": user_id,
            'step': step,
            "isSelectBlock": isSelectBlock,
            "selectValue": select_value,
            "contextLevel": context_level,
            "typeContext": typeContext,
            "testType": testType,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "tokens": total_tokens,
            "max_tokens": max_tokens,
            "message": updated_messages
        }
        
        # Preparar documento para MongoDB
        message_to_save = {
            "_id": conversation_id,
            "data": {
                "conversationId": conversation_id,
                "nameHistory": name_history,
                "userID": user_id,
                "step": step,
                "isSelectBlock": isSelectBlock,
                "selectValue": select_value,
                "typeContext": typeContext,
                "testType": testType,
                "tokens_input": tokens_input,
                "tokens_output": tokens_output,
                "tokens": total_tokens,
                "max_tokens": max_tokens,
                "message": [
                    msg for msg in updated_messages 
                    if msg['role'] in ["user", "assistant", "system"]
                ]
            }
        }
        # Guardar en MongoDB
        self.mongo_repo.save_conversation(message_to_save)
        self.logger.info("conversaciones guardados en MongoDB.")
        
        # Guardar la conversación en la historia
        self.conversation_history[conversation_id] = updated_messages
        self.conversation_manager.save_conversation(conversation_id, user_message, name_history, is_valid_context)

        self.logger.info("Conversación guardada exitosamente.")

        return {"data": response_data}, 200

    def validate_context(self, context: str) -> bool:
        self.logger.debug(f"Validando contexto: {context}")
        validation_prompt = self.prompt_validation_context(context)
        self.logger.debug(f"Prompt de validación generado: {validation_prompt}")
        response_tuple = self.llm.generate_response(validation_prompt)

        # Asumimos que la respuesta está en el primer elemento de la tupla
        if isinstance(response_tuple, tuple) and len(response_tuple) > 0:
            response = response_tuple[0]
        else:
            response = str(response_tuple)  

        self.logger.debug(f"Respuesta del LLM: {response}")
        return response.strip().lower() == 'true'
    
    def prompt_validation_context(self, context: str) -> str:
        return f"""
        El contexto proporcionado debe estar relacionado con un negocio, empresa o plan de trabajo.
        Asegúrate de que el contexto sea claro, específico y relevante para un entorno empresarial.
        
        Contexto actual: {context}
        
        Considera los siguientes criterios al evaluar el contexto:
        - ¿Describe de manera clara las funciones y responsabilidades relacionadas con el negocio?
        - ¿Proporciona detalles sobre los procesos y métodos utilizados?
        - ¿Establece conexiones claras entre los objetivos y los resultados esperados?
        - ¿Es relevante para las operaciones o estrategias de la empresa?
        
        ¿Este contexto cumple con los criterios mencionados?
        Responde únicamente con 'true' si cumple o 'false' si no cumple, sin ninguna explicación adicional.
        """