
from src.ports.output_ports.chromadb_repository_port import ChromaDbRepositoryPort
from src.ports.test_cases_ports.process_context_port import ProcessContextPort
from src.ports.test_cases_ports.process_context_api_port import ProcessContextApiPort
from src.ports.test_cases_ports.process_user_story_port import ProcessUserStoryPort
from src.ports.test_cases_ports.process_user_story_api_port import ProcessUserStoryAPIPort

from pymongo.errors import PyMongoError
import logging
from datetime import datetime
import json
import uuid

class TestCaseGeneratorService:
    def __init__(self, process_context: ProcessContextPort, process_user_story: ProcessUserStoryPort, 
                 process_context_api: ProcessContextApiPort, process_user_story_api: ProcessUserStoryAPIPort):
        self.process_context = process_context
        self.process_user_story = process_user_story
        self.process_context_api = process_context_api
        self.process_user_story_api = process_user_story_api
        self.logger = logging.getLogger(__name__)
        self.logger.info("TestCaseGeneratorService initialized")
        self.conversation_history = {}

    def generate_test_cases(self, input_data):
        type_context = input_data['data'].get('typeContext')
        test_type = input_data['data'].get('testType')
        conversation_id = input_data['data'].get('conversation_id') or str(uuid.uuid4())
        user_message = input_data['data']['message'][-1]['content']
        previous_messages = input_data['data'].get('previous_messages', [])
        context_level = input_data['data'].get('contextLevel')

        # Verificar que 'typeContext' sea válido
        if type_context not in ["GenerateTestFunctional", "GenerateTestFunctionalApi"]:
            return {"error": f"Tipo de contexto no válido: {type_context}"}, 400
        
        # Proceso de validación de contextos
        if test_type == 'context':
            if type_context == "GenerateTestFunctional":
                
                return self.process_context._process_context(input_data, conversation_id, user_message, previous_messages)

            elif type_context == "GenerateTestFunctionalApi":

                if context_level == "business":
                    
                    return self.process_context._process_context(input_data, conversation_id, user_message, previous_messages)

                elif context_level == "technical":
                    
                    return self.process_context_api._process_context(input_data, conversation_id, user_message, previous_messages)
                
                else:
                    return {"error": "Nivel de contexto no válido. Use 'business' o 'technical'."}, 400

        elif test_type == 'user_story':
            if type_context == "GenerateTestFunctional":
                return self.process_user_story._process_user_story(input_data)
            
            elif type_context == "GenerateTestFunctionalApi":
                
                return self.process_user_story_api._process_user_story(input_data)

        return {"error": "Tipo de prueba no válido"}, 400