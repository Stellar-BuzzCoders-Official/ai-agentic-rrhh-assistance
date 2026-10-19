import os
import google.generativeai as genai
from src.ports.output_ports.llm_port import LLMPort

class GeminiRepository(LLMPort):
    def __init__(self):
        print("Inicializando GeminiRepository...")
        # Leer configuración desde variables de entorno
        self.api_key = os.getenv("GEMINI_API_KEY",)
        self.model_name = os.getenv("GEMINI_MODEL")

        # Validar que las configuraciones requeridas estén presentes
        if not self.api_key:
            raise ValueError("Falta la configuración de GEMINI_API_KEY en las variables de entorno.")

        genai.configure(api_key=self.api_key)
        
        # Configuración del modelo
        self.generation_config = {
            "temperature": 1,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
            "response_mime_type": "text/plain",
        }

        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=self.generation_config,
        )

        print(f"GeminiRepository inicializado con el modelo: {self.model_name}.")

    def generate_response(self, prompt: str) -> str:
        print(f"Generando respuesta para prompt: {prompt[:50]}...")
        try:
            # Iniciar una sesión de chat
            chat_session = self.model.start_chat(history=[])
            
            # Enviar el mensaje al modelo
            response = chat_session.send_message(prompt)

            # Retornar la respuesta del modelo
            ai_response = response.text
            print(f"Respuesta generada: {ai_response[:50]}...")
            return ai_response
        except Exception as e:
            print(f"Error al generar respuesta: {e}")
            raise RuntimeError("Ocurrió un error al generar la respuesta con Gemini.") from e
