# src/adapters/test_case_prompt_generator_adapter.py
from src.ports.output_ports.llm_port import LLMPort
from src.ports.test_cases_ports.test_case_prompt_generator_port import TestCasePromptGeneratorPort
import logging

class TestCasePromptGeneratorAdapter(TestCasePromptGeneratorPort):
    def __init__(self, llm: LLMPort,):
        self.logger = logging.getLogger(__name__)
        self.logger.info("TestCaseGeneratorService initialized")
        self.llm = llm
        
    def promt_generate_test_cases(self, context: str, user_story: str) -> str:
        """Genera el prompt y llama a ollama_llm para generar los casos de prueba en formato Markdown tipo CSV."""
        prompt = f"""
        Eres un Ingeniero de QA experto. Tu tarea es generar casos de prueba exhaustivos para la siguiente historia de usuario, considerando el contexto proporcionado. Asegúrate de cubrir todos los aspectos relevantes y escenarios posibles, tanto positivos como negativos.
        
        Historia de usuario:
        "{user_story}"
        
        Contexto adicional:
        "{context}"
        
        Instrucciones:
        1. Genera una única tabla de casos de prueba en formato Markdown.
        2. Inicia la tabla con la etiqueta **csv** en una línea separada.
        3. La tabla debe tener las siguientes columnas:
        | Status | Priority | Labels | Description | Step Summary | Test Data | Expected Result |
        4. Utiliza estas reglas para llenar la tabla:
        - Status: Siempre "To Do"
        - Priority: Elige entre Highest, High, Medium, Low, Lowest
        - Labels: Nombre o etiqueta de caso de prueba. (opcional)
        - Description: Obligatorio, describe el caso de prueba
        - Step Summary: Obligatorio, enumera los pasos a seguir. Si los pasos están numerados, cada paso numerado debe estar en una nueva línea usando '<br />' para los saltos de línea. Si no hay numeración, los pasos pueden ir en una sola línea.
        - Test Data: Entorno de testeo del caso de prueba. Por ejemplo página web (opcional)
        - Expected Result: Obligatorio, describe el resultado esperado
        5. Después de la última fila de la tabla, cierra con otra etiqueta **csv** en una línea separada.
        6. Asegúrate de que la tabla esté correctamente formateada en Markdown.
        7. No incluyas explicaciones adicionales, solo la tabla de casos de prueba entre las etiquetas csv.
        
        El formato final debe ser exactamente así:
        
        **csv**
        | Summary | Status | Priority | Labels | Description | Step Summary | Test Data | Expected Result |
        | --- | --- | --- | --- | --- | --- | --- | --- |
        | [Summary] | To Do | [Priority] | [Labels] | [Description] | 1. Primer paso<br />2. Segundo paso<br />3. Tercer paso | [Test Data] | [Expected Result] |
        | [Summary] | To Do | [Priority] | [Labels] | [Description] | Realizar acción A, luego acción B, finalmente acción C | [Test Data] | [Expected Result] |
        ... (más filas según sea necesario)
        **csv**
        """
        
        test_cases = self.llm.generate_response(prompt)
        
        return test_cases