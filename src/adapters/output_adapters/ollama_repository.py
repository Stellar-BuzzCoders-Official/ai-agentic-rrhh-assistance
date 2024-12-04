from src.ports.output_ports.llm_port import LLMPort

import ollama 

class OllamaRepository(LLMPort):
    def __init__(self):
        print("Inicializando OllamaRepository...")
        # No se necesita inicializar ChromaDB
        print("OllamaRepository inicializado correctamente.")
        
    def generate_response(self, prompt:  None) -> str:
        print(f"Generando respuesta para prompt: {prompt[:50]}...")
        
        # Llamando a ollama.chat directamente con el prompt
        print("Llamando a ollama.chat...")
        response = ollama.chat(
            model="llama3.1:8b",
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.1}
        )
        
        ai_response = response['message']['content']
        print(f"Respuesta generada: {ai_response[:50]}...")
        
        return ai_response