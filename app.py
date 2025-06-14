from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import ollama as ollama
from src.adapters.input_adapters import APIController
from src.services import TechnicalReportGeneratorService
from src.adapters.output_adapters import OllamaRepository, AzureRepository, GeminiRepository
from src.adapters.output_adapters import MongoDBRepository
from src.adapters.tech_profile_adapters import ProcessRequestRequirementsAdapter
from src.adapters.tech_profile_adapters import ProcessCvAdapter
from src.adapters.tech_profile_adapters.technical_report_prompt_generator_adapter import TestCasePromptGeneratorAdapter
from src.adapters.conversation_adapters.name_history_generator_adapter import NameHistoryGeneratorAdapter
from src.adapters.conversation_adapters.conversation_management_adapter import ConversationManagementAdapter
import logging
from src.adapters.tech_profile_adapters.count_tokens_adapter import CountTokensAdapter
from pymongo.errors import PyMongoError
from dotenv import load_dotenv
import os
from typing import Dict, Any, List
from pydantic import BaseModel
import asyncio
import uvicorn

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Crear la aplicación FastAPI
app = FastAPI(
    title="Screening API",
    description="API de Screening con FastAPI",
    version="1.0.0",
    debug=True
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especifica los orígenes permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar repositorios y servicios
mongo_repo = MongoDBRepository()
FLAGGER_MODEL = os.getenv('FLAGGER_MODEL')

# Instanciar el LLM basado en FLAGGER_MODEL
if FLAGGER_MODEL == 'azureml':
    llm = AzureRepository()
    logger.info("Usando AzureML como proveedor de LLM.")
elif FLAGGER_MODEL == 'ollama':
    llm = OllamaRepository()
    logger.info("Usando Ollama como proveedor de LLM.")
elif FLAGGER_MODEL == 'geminilm':
    llm = GeminiRepository()
    logger.info("Usando GeminiLM como proveedor de LLM.")
else:
    raise ValueError(f"El modelo FLAGGER_MODEL '{FLAGGER_MODEL}' no es soportado.")

# Inicializar adaptadores y servicios
count_tokens = CountTokensAdapter()
conversation_manager = ConversationManagementAdapter(mongo_repo)
name_history_generator = NameHistoryGeneratorAdapter(llm)
prompt_generator = TestCasePromptGeneratorAdapter(llm)
process_request_requirements = ProcessRequestRequirementsAdapter(
    llm, mongo_repo, name_history_generator, conversation_manager, count_tokens
)
process_request_cv = ProcessCvAdapter(
    llm, mongo_repo, prompt_generator, conversation_manager, count_tokens
)
test_case_generator_service = TechnicalReportGeneratorService(
    process_request_requirements, process_request_cv
)
api_controller = APIController(test_case_generator_service)

# Modelos Pydantic para validación de entrada
class ScreeningRequest(BaseModel):
    # Agrega los campos necesarios según tu estructura de datos
    pass

class UserData(BaseModel):
    # Agrega los campos necesarios para crear un usuario
    pass

# Función auxiliar para ejecutar código síncrono de forma asíncrona
async def run_in_executor(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)

# Endpoints

@app.get("/")
async def root():
    """Endpoint raíz de bienvenida"""
    return {"message": "Bienvenido a la API de Screening."}

@app.post("/api/v0/screeningChat")
async def screening_chat(request: Request):
    """Endpoint para generar casos de prueba"""
    try:
        input_data = await request.json()
        logger.info("Iniciando la generación de casos de prueba.")
        
        # Ejecutar el controlador de forma asíncrona
        response, status_code = await run_in_executor(
            api_controller.generate_test_cases, input_data
        )
        
        logger.debug(f"Respuesta generada: {response}, Código de estado: {status_code}")
        return JSONResponse(content=response, status_code=status_code)
        
    except ValueError as e:
        logger.error(f"Error de valor: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error interno: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ocurrió un error interno del servidor.")

@app.get("/api/v0/conversationsIdName/{user_id}")
async def get_conversations(user_id: str):
    """Obtener conversaciones filtradas por ID de usuario"""
    try:
        # Verificar si el usuario existe
        user = await run_in_executor(mongo_repo.get_user_by_id, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        conversations = await run_in_executor(mongo_repo.get_all_conversations, user_id)
        filtered_conversations = []
        
        for conversation in conversations:
            filtered_conversation = {
                "_id": str(conversation.get('_id')),
                "nameHistory": conversation.get('data', {}).get('nameHistory')
            }
            filtered_conversations.append(filtered_conversation)

        return filtered_conversations
        
    except HTTPException:
        raise
    except (PyMongoError, Exception) as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error al recuperar las conversaciones: {str(e)}"
        )

@app.get("/api/v0/getConversation/{conversation_id}")
async def get_conversation_by_id(conversation_id: str):
    """Obtener una conversación por su ID"""
    try:
        conversation = await run_in_executor(mongo_repo.get_conversation_by_id, conversation_id)
        if conversation:
            return conversation
        else:
            raise HTTPException(status_code=404, detail="Conversación no encontrada")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_all_conversations/{user_id}")
async def get_all_conversations(user_id: str):
    """Obtener todas las conversaciones de un usuario"""
    try:
        conversations = await run_in_executor(mongo_repo.get_all_conversations, user_id)
        return {"conversations": conversations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v0/deleteConversation/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Eliminar una conversación por su ID"""
    try:
        result = await run_in_executor(mongo_repo.delete_conversation, conversation_id)
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=404, 
                detail=f"La conversación con _id {conversation_id} no fue encontrada."
            )
        return {"message": f"La conversación con _id {conversation_id} ha sido eliminada."}
    except HTTPException:
        raise
    except (PyMongoError, Exception) as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error al eliminar la conversación: {str(e)}"
        )

@app.delete("/api/v0/deleteHistoryConversations/{user_id}")
async def delete_history(user_id: str):
    """Eliminar todas las conversaciones de un usuario"""
    try:
        user = await run_in_executor(mongo_repo.get_user_by_id, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        response, status_code = await run_in_executor(
            mongo_repo.delete_history_conversation, user_id
        )
        return JSONResponse(content=response, status_code=status_code)
    except HTTPException:
        raise
    except (PyMongoError, Exception) as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error al eliminar el historial de conversaciones: {str(e)}"
        )

@app.post("/api/v0/createUser")
async def create_user(request: Request):
    """Crear un nuevo usuario"""
    try:
        user_data = await request.json()
        if not user_data:
            raise HTTPException(status_code=400, detail="Datos del usuario no proporcionados")
        
        result = await run_in_executor(mongo_repo.save_user, user_data)
        if result and isinstance(result, str):
            return {
                "message": "Usuario creado correctamente",
                "userId": result
            }
        else:
            logger.info("Usuario creado correctamente")
            return {"message": "Usuario creado correctamente"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al crear usuario: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al crear usuario: {str(e)}")

@app.get("/api/v0/getAllUsers")
async def get_all_users():
    """Obtener todos los usuarios"""
    try:
        users = await run_in_executor(mongo_repo.get_all_users)
        
        if users:
            return {"users": users}
        else:
            raise HTTPException(status_code=404, detail="No users found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v0/deleteUsers")
async def delete_all_users():
    """Eliminar todos los usuarios"""
    try:
        deleted_count = await run_in_executor(mongo_repo.delete_all_users)
        return {
            "message": f"Se han borrado {deleted_count} usuarios exitosamente.",
            "deleted_count": deleted_count
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Ha ocurrido un error al intentar borrar todos los usuarios.",
                "details": str(e)
            }
        )

@app.get("/api/v0/getCapability/{capability_id}")
async def get_capability_by_id(capability_id: str):
    """Obtener una capacidad por su ID"""
    try:
        capability = await run_in_executor(mongo_repo.get_capability_by_id, capability_id)
        if capability:
            return capability
        else:
            raise HTTPException(status_code=404, detail="Capacidad no encontrada")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v0/getCapabilities")
async def get_all_capabilities():
    """Obtener todas las capacidades"""
    try:
        capabilities = await run_in_executor(mongo_repo.get_all_capabilities)
        return {"capabilities": capabilities}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v0/deleteCapabilities")
async def delete_all_capabilities():
    """Eliminar todas las capacidades"""
    try:
        deleted_count = await run_in_executor(mongo_repo.delete_all_capabilities)
        return {
            "message": f"Se han borrado {deleted_count} capacidades exitosamente.",
            "deleted_count": deleted_count
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Ha ocurrido un error al intentar borrar todas las capacidades.",
                "details": str(e)
            }
        )

@app.get("/api/v0/capabilities/{conversation_id}")
async def get_capabilities(conversation_id: str):
    """Obtener capacidades por ID de conversación"""
    try:
        capabilities = await run_in_executor(
            mongo_repo.get_capabilities_by_conversation_id, conversation_id
        )

        if not capabilities:
            raise HTTPException(
                status_code=404, 
                detail="No se encontraron capacidades para la conversación solicitada."
            )
        
        return capabilities
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error al obtener capacidades: {str(e)}"
        )

# Manejador de excepciones global
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Error no manejado: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor"}
    )

if __name__ == '__main__':
    print("Iniciando la aplicación FastAPI...")
    uvicorn.run(
        "main:app",
        host='0.0.0.0',
        port=5000,
        reload=True,
        log_level="info"
    )