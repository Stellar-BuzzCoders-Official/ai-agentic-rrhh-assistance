from src.ports.output_ports.llm_port import LLMPort

import ollama 

class OllamaRepository(LLMPort):
    def __init__(self):
        print("Inicializando OllamaRepository...")
        # No se necesita inicializar ChromaDB
        print("OllamaRepository inicializado correctamente.")
        
    def generate_response(self, prompt: str) -> str:
        print(f"Generando respuesta para prompt: {prompt[:50]}...")
        
        # Llamando a ollama.chat directamente con el prompt
        print("Llamando a ollama.chat...")
        try:
            response = ollama.chat(
                model="llama3.1:8b",
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.1}
            )
            print("Conexión con el modelo exitosa.")
        except Exception as e:
            print(f"Error al conectar con el modelo: {e}")
            return "Error al generar respuesta."
        
        ai_response = response['message']['content']
        print(f"Respuesta generada: {ai_response[:50]}...")
        
        return ai_response