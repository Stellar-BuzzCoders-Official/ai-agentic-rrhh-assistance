# src/adapters/test_case_prompt_generator_adapter.py
from src.ports.output_ports.llm_port import LLMPort
from src.ports.test_cases_ports.test_case_prompt_generator_port import TestCasePromptGeneratorPort
import logging

class TestCasePromptGeneratorAdapter(TestCasePromptGeneratorPort):
    def __init__(self, llm: LLMPort,):
        self.logger = logging.getLogger(__name__)
        self.logger.info("TestCaseGeneratorService initialized")
        self.llm = llm
        
    def promt_generate_technical_report(self, capabilities: str, request_cv: str) -> str:
        """Genera el informe técnico en formato CSV basado en el CV del participante y las capacidades proporcionadas."""
        
        prompt = f"""
        Eres un reclutador técnico especializado con amplia experiencia en evaluación de perfiles tecnológicos.

        Tu tarea es generar un informe técnico detallado en formato CSV basado en el CV del participante y las capacidades proporcionadas.

        CV proporcionado:
        {request_cv}

        Capacidades requeridas:
        {capabilities}

        Instrucciones de generación:
        1. Extrae la información personal del candidato del CV proporcionado
        2. Identifica las capacidades técnicas del candidato
        3. Genera una tabla en formato CSV que mapee estas capacidades
        4. Para cada capacidad, determina:
        - Si cumple con los requisitos
        - El nivel de conocimiento o experiencia
        - Comentarios adicionales que contextualicen su expertise

        Formato de salida:
        **csv**
        Nombre, Posición, Cliente, Años de Experiencia, Capacidad Técnica, Tipo, Nivel, Estado, Comentarios Adicionales
        [Datos extraídos del CV], [Capacidad Técnica], [Indispensable/Deseable], [Conocimiento/Experiencia], [Cumple/No Cumple], [Comentario Explicativo]
        **csv**

        Consideraciones importantes:
        - Sé preciso y objetivo en la evaluación
        - Basa tus observaciones únicamente en la información proporcionada
        - Si no hay información suficiente, indica "No verificable"
        - Prioriza la relevancia y el contexto técnico
        """
        
        # Generar la respuesta con el modelo LLM basado en el prompt
        technical_report = self.llm.generate_response(prompt)
        
        return technical_report
