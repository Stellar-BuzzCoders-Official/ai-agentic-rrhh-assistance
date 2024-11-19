from abc import ABC, abstractmethod

class TestCasePromptGeneratorApiPort:
    @abstractmethod
    def promt_generate_test_cases(self, context_business: str, context_technical: str, user_story: str) -> str:
        """Genera casos de prueba basados en el contexto y la historia de usuario proporcionados."""
        pass