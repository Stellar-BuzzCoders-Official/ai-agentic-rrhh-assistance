from src.ports.input_ports import APIPort
from src.services import TestCaseGeneratorService
from src.domain.entities import UserStory

class APIController(APIPort):
    def __init__(self, test_case_generator_service: TestCaseGeneratorService):
        self.test_case_generator_service = test_case_generator_service
    
    def generate_test_cases(self, user_story: UserStory) -> str:
        return self.test_case_generator_service.generate_test_cases(user_story)
    def generate_context(self, context_data: UserStory) -> str:
        return self.test_case_generator_service.save_context(context_data)
    def generate_assistant_message(self, is_valid_context) -> str:
        return self.test_case_generator_service.generate_assistant_message(is_valid_context)
    def validate_request_data(self, data) -> str:
        return self.test_case_generator_service.validate_request_data(data)
    def save_context(self, data) -> str:
        return self.test_case_generator_service.save_context(data)
    def generate_name(self, content_user) -> str:
        return self.test_case_generator_service.generate_name(content_user)