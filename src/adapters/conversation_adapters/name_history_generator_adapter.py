# src/adapters/name_history_generator_adapter.py

from src.ports.conversation_ports.name_history_generator_port import NameHistoryGeneratorPort
from src.ports.output_ports.llm_port import LLMPort

class NameHistoryGeneratorAdapter(NameHistoryGeneratorPort):
    def __init__(self, llm: LLMPort):
        self.llm = llm

    def generate_name_history(self, request_requirements):
        prompt = (
            f"Dado el siguiente contexto:\n\n{request_requirements}\n\n"
            "Crea un nombre claro, breve y relevante relacionado directamente con el tema. "
            "El nombre debe tener un máximo de cuatro palabras, no incluir explicaciones, etiquetas, ni texto adicional. "
            "Ejemplo de salida esperada: 'Gestor de Casos'. Devuelve únicamente el nombre sin formato adicional."
        )

        name_history = self.llm.generate_response(prompt)

        # Limpieza del resultado
        if isinstance(name_history, tuple):  
            name_history = name_history[0]

        name_history = name_history.strip()  

        # Filtrar contenido adicional
        unwanted_phrases = ["**", ":", "\n"]
        for phrase in unwanted_phrases:
            name_history = name_history.replace(phrase, "").strip()

        return name_history