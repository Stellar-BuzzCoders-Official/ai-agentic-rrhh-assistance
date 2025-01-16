from src.ports.output_ports.llm_port import LLMPort
import os
from openai import AzureOpenAI
import time
import openai


class AzureRepository(LLMPort):
    def __init__(self):
        print("Inicializando AzureRepository...")
        # Leer configuración de Azure desde variables de entorno
        self.azure_endpoint = os.getenv('AZURE_ENDPOINT', '').rstrip('/')
        self.azure_api_key = os.getenv('AZURE_API_KEY', '')
        self.azure_deployment = os.getenv('AZURE_DEPLOYMENT', '')

        # Validar que las configuraciones requeridas estén presentes
        if not all([self.azure_endpoint, self.azure_api_key, self.azure_deployment]):
            raise ValueError("Faltan configuraciones necesarias para Azure OpenAI en las variables de entorno.")

        # Configurar cliente AzureOpenAI
        self.azure_client = AzureOpenAI(
            azure_endpoint=self.azure_endpoint,
            api_key=self.azure_api_key,
            api_version="2024-05-01-preview"
        )
        print("AzureRepository inicializado correctamente.")

    def generate_response(self, prompt: str) -> str:
        print(f"Generando respuesta para prompt: {prompt[:50]}...")
        retries = 0
        max_retries = 5
        initial_retry_delay = 1  

        while retries < max_retries:
            try:
                # Llamar al modelo Azure OpenAI con el prompt
                response = self.azure_client.chat.completions.create(
                    model=self.azure_deployment,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    top_p=0.95
                )
                ai_response = response.choices[0].message.content
                print(f"Respuesta generada: {ai_response[:50]}...")
                return ai_response
            except openai.RateLimitError as e:
                retries += 1
                delay = initial_retry_delay * (2 ** retries)
                print(f"RateLimitError detectado. Reintentando {retries}/{max_retries} en {delay:.2f} segundos...")
                time.sleep(delay)
            except openai.OpenAIError as e:
                print(f"Error general de OpenAI: {e}")
                raise
            except Exception as e:
                print(f"Error inesperado: {e}")
                raise

        raise RuntimeError("Se alcanzó el límite de reintentos para generar respuesta.")