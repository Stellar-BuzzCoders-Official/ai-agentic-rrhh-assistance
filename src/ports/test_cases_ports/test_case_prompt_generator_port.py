# src/ports/test_cases_ports/test_case_prompt_generator_port.py

from abc import ABC, abstractmethod

class TestCasePromptGeneratorPort(ABC):
    @abstractmethod
    def prompt_generate_technical_report(self, capabilities: str, request_cv: str) -> str:
        """Genera el informe técnico de una historia de usuario."""
        pass
