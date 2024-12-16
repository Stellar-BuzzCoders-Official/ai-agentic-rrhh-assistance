
from src.ports.output_ports.llm_port import LLMPort
from src.ports.test_cases_ports.test_case_prompt_generator_port import TestCasePromptGeneratorPort
import logging
import json
import re

class TestCasePromptGeneratorAdapter(TestCasePromptGeneratorPort):
    def __init__(self, llm: LLMPort):
        self.logger = logging.getLogger(__name__)
        self.logger.info("TestCaseGeneratorService initialized")
        self.llm = llm

    def prompt_generate_technical_report(self, capabilities: str, request_cv: str) -> dict:
        """Genera el informe técnico en formato JSON basado en el CV del participante y las capacidades proporcionadas."""
        prompt = f"""
    IMPORTANTE: Tu respuesta DEBE ser ÚNICAMENTE un JSON válido. NO incluyas NINGÚN texto adicional antes o después del JSON.

    Instrucciones para generar el informe técnico:
    1. Analiza el CV proporcionado
    2. Evalúa las capacidades requeridas
    3. Genera un JSON estructurado que siga EXACTAMENTE este formato

    CV proporcionado:
    {request_cv}

    Capacidades requeridas:
    {capabilities}

    Genera SOLO el siguiente JSON:
    {{
        "personalInfo": {{
            "name": "Nombre del candidato extraído del CV",
            "position": "Posición o rol del candidato",
            "client": "",
            "experienceYears": 0
        }},
        "technicalCapabilities": [
            {{
                "category": "designAndPatterns",
                "skills": [
                    {{
                        "name": "softwareDesignAnalysis",
                        "type": "Indispensable",
                        "level": "Conocimiento",
                        "status": "Cumple"
                    }}
                ]
            }}
        ],
        "evaluationSummary": {{
            "requiredSkillsMet": 3,
            "optionalSkillsMet": 1,
            "additionalNotes": "Notas importantes sobre la evaluación del candidato"
        }}
    }}

    REGLAS ESTRICTAS:
    - Responde SOLO con el JSON
    - No uses texto descriptivo
    - No agregues comentarios
    - Completa todos los campos con información real del CV
    - Si no hay información, usa valores por defecto o "No verificable"
    - Asegúrate de que el JSON sea 100% válido
    """

        response = self.llm.generate_response(prompt)
        
        
        def extract_json(text):
            """
            Extrae un JSON válido de un texto que puede contener otros elementos.
            """
            import json
            import re

            # Buscar el JSON dentro del texto usando expresiones regulares
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                try:
                    # Intentar parsear el JSON encontrado
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError as e:
                    logging.error(f"Error al parsear JSON: {e}")
            
            # Si no se encuentra un JSON válido, registrar el problema
            logging.error(f"No se pudo extraer un JSON válido. Texto original: {text}")
            raise ValueError("No se encontró un JSON válido en la respuesta.")

        response = self.llm.generate_response(prompt)

        # Extraer y devolver el JSON
        try:
            json_response = extract_json(response)
            return json_response
        except ValueError as e:
            self.logger.error(f"Error al extraer JSON: {e}")
            raise

    
    def clean_text(self, text):
        """
        Limpia el texto eliminando caracteres no válidos o innecesarios, 
        incluyendo comentarios y extrayendo solo el JSON.
        """
        try:
            # Primero, intentar extraer JSON directo
            import json
            # Try to parse the entire text as JSON first
            json.loads(text)
            return text
        except json.JSONDecodeError:
            # Elimina caracteres no imprimibles
            cleaned_text = re.sub(r'[^\x20-\x7E]', '', text)  # Solo permite caracteres ASCII imprimibles
            # Elimina espacios múltiples
            cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
            
            # Elimina los comentarios de línea (//) y bloque (/* ... */)
            cleaned_text = re.sub(r'//.*', '', cleaned_text)  # Elimina comentarios de línea
            cleaned_text = re.sub(r'/\*.*?\*/', '', cleaned_text, flags=re.DOTALL)  # Elimina comentarios de bloque
            
            # Intentar encontrar JSON de múltiples formas
            json_patterns = [
                r'```json\n(.*?)\n```',  # Buscar dentro de bloques ```json```
                r'{.*?}',  # Buscar cualquier objeto JSON
                r'\n(\{.*?\})\n'  # Buscar JSON entre líneas nuevas
            ]
            
            for pattern in json_patterns:
                match = re.search(pattern, cleaned_text, re.DOTALL | re.MULTILINE)
                if match:
                    json_str = match.group(1) if match.groups() else match.group(0)
                    try: 
                        # Validar que es un JSON válido
                        json.loads(json_str)
                        return json_str.strip()
                    except json.JSONDecodeError:
                        continue
            
            # Si no se encuentra un JSON válido, registrar el problema
            self.logger.error(f"No se pudo extraer un JSON válido. Texto original: {text}")
            raise ValueError("No se encontró un JSON válido en la respuesta.")