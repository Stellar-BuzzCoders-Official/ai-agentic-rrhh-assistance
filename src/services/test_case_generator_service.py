
from src.ports.test_cases_ports.process_request_requirements_port import ProcessRequestRequirementsPort
from src.ports.test_cases_ports.process_user_story_port import ProcessUserStoryPort
from src.ports.test_cases_ports.process_user_story_api_port import ProcessUserStoryAPIPort

from pymongo.errors import PyMongoError
import logging
from datetime import datetime
import json
import uuid

class TestCaseGeneratorService:
    def __init__(self, process_request_requirements: ProcessRequestRequirementsPort, process_user_story: ProcessUserStoryPort):
        self.process_request_requirements = process_request_requirements
        self.process_user_story = process_user_story
        self.logger = logging.getLogger(__name__)
        self.logger.info("TestCaseGeneratorService initialized")
        self.conversation_history = {}

    def generate_test_cases(self, input_data):
        process_phase = input_data['data'].get('process_phase')
        conversation_id = input_data['data'].get('conversation_id') or str(uuid.uuid4())
        user_message = input_data['data']['message'][-1]['content']
        previous_messages = input_data['data'].get('previous_messages', [])
        context_level = input_data['data'].get('contextLevel')

        # Verificar que 'typeContext' sea válido
        if process_phase not in ["request_requirements", "upload_cv_and_match"]:
            return {"error": f"Tipo de contexto no válido: {process_phase}"}, 400
        
        # Proceso de validación de contextos
        if process_phase == 'request_requirements':
                
                return self.process_request_requirements._process_request_requirements(input_data, conversation_id, user_message, previous_messages)

        elif process_phase == 'upload_cv_and_match':
                
                return self.process_user_story._process_user_story(input_data)

        return {"error": "Tipo de prueba no válido"}, 400