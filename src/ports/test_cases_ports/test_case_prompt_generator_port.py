# src/ports/test_cases_ports/test_case_prompt_generator_port.py

from abc import ABC, abstractmethod

class TestCasePromptGeneratorPort(ABC):
    @abstractmethod
    def promt_generate_test_cases(self, context: str, user_story: str) -> str:
        """Genera casos de prueba basados en el contexto y la historia de usuario proporcionados."""
        pass
