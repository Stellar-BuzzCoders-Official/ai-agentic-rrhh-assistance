from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
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
from datetime import datetime, timedelta  # ← ASEGÚRATE DE TENER ESTA LÍNEA

# Importar el adaptador JWT
from src.adapters.output_adapters.JWTAuthAdapter import JWTAuthAdapter  # Ajusta la ruta según tu estructura

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

# Inicializar adaptador JWT
jwt_auth = JWTAuthAdapter()
security = HTTPBearer()

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
class LoginRequest(BaseModel):
    username: str
    password: str

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

# Dependencia para verificar autenticación
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verifica el token JWT y retorna los datos del usuario actual"""
    try:
        token = credentials.credentials
        payload = jwt_auth.verify_token(token)
        return payload
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en autenticación: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Endpoints públicos (sin autenticación)

@app.get("/")
async def root():
    """Endpoint raíz de bienvenida"""
    return {"message": "Bienvenido a la API de Screening."}

@app.post("/api/v0/auth/login")
async def login(login_request: LoginRequest):
    """Endpoint para autenticar usuario y generar token"""
    try:
        # Autenticar usuario
        user_data = await run_in_executor(
            jwt_auth.authenticate_user, 
            mongo_repo, 
            login_request.username, 
            login_request.password
        )
        
        if not user_data:
            raise HTTPException(
                status_code=401,
                detail="Credenciales incorrectas"
            )
        
        # Crear respuesta con token
        response = jwt_auth.create_login_response(user_data)
        
        logger.info(f"Login exitoso para usuario: {login_request.username}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en login: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error interno en el proceso de login"
        )

@app.post("/api/v0/auth/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Endpoint para cerrar sesión (logout)"""
    try:
        # En un sistema JWT stateless, el logout se maneja del lado del cliente
        # eliminando el token. Aquí puedes agregar lógica adicional si es necesario
        # como invalidar el token en una blacklist, etc.
        
        logger.info(f"Logout exitoso para usuario: {current_user.get('username')}")
        return {
            "message": "Logout exitoso",
            "detail": "Token invalidado. Elimine el token del lado del cliente."
        }
        
    except Exception as e:
        logger.error(f"Error en logout: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error interno en el proceso de logout"
        )

@app.post("/api/v0/createUser")
async def create_user(request: Request):
    """Crear un nuevo usuario (público o privado según necesidad)"""
    try:
        user_data = await request.json()
        logger.info(f"Datos recibidos: {user_data}")
        
        if not user_data:
            raise HTTPException(status_code=400, detail="Datos del usuario no proporcionados")

        # Validar campos obligatorios
        required_fields = ["email", "userName", "userID"]
        for field in required_fields:
            if field not in user_data:
                raise HTTPException(status_code=400, detail=f"Campo requerido faltante: {field}")

        # DEBUG: Verificar si existe la contraseña
        logger.info(f"¿Existe 'password' en user_data? {'password' in user_data}")
        if 'password' in user_data:
            logger.info(f"Valor de password antes del hash: {user_data['password']}")

        # HASHEAR LA CONTRASEÑA
        if "password" in user_data and user_data["password"]:
            # Verificar que la contraseña no esté vacía
            password_original = user_data["password"]
            logger.info(f"Contraseña original recibida: {password_original}")
            
            if not password_original.strip():
                raise HTTPException(status_code=400, detail="La contraseña no puede estar vacía")
            
            # DEBUG: Verificar que jwt_auth existe
            logger.info(f"jwt_auth object: {jwt_auth}")
            logger.info(f"jwt_auth.hash_password method: {jwt_auth.hash_password}")
            
            # Hashear la contraseña usando el adaptador JWT
            try:
                hashed_password = jwt_auth.hash_password(password_original)
                logger.info(f"Contraseña hasheada exitosamente. Hash: {hashed_password[:20]}...")
                user_data["password"] = hashed_password
                logger.info(f"Password en user_data después del hash: {user_data['password'][:20]}...")
            except Exception as hash_error:
                logger.error(f"Error al hashear contraseña: {hash_error}")
                raise HTTPException(status_code=500, detail=f"Error al procesar contraseña: {str(hash_error)}")
                
        else:
            logger.warning("No se encontró contraseña en los datos o está vacía")
            raise HTTPException(status_code=400, detail="La contraseña es requerida")

        # Verificar if ya existe un usuario con el mismo userName
        logger.info(f"Verificando si existe usuario: {user_data['userName']}")
        existing_user = await run_in_executor(
            mongo_repo.find_one, 
            "users",  # nombre de la colección
            {"userName": user_data["userName"]}  # filtro de búsqueda
        )
        if existing_user:
            logger.warning(f"Usuario ya existe: {user_data['userName']}")
            raise HTTPException(status_code=409, detail="El usuario ya existe")

        # También verificar por email si es diferente del userName
        if user_data["email"] != user_data["userName"]:
            existing_email = await run_in_executor(mongo_repo.find_one, "users", {"email": user_data["email"]})
            if existing_email:
                logger.warning(f"Email ya está en uso: {user_data['email']}")
                raise HTTPException(status_code=409, detail="El email ya está en uso")

        # Agregar campos adicionales
        from datetime import datetime
        user_data["created_at"] = datetime.utcnow().isoformat()
        user_data["is_active"] = True
        
        # DEBUG: Ver los datos finales antes de guardar
        user_data_copy = user_data.copy()
        user_data_copy["password"] = user_data_copy["password"][:20] + "..." if len(user_data_copy["password"]) > 20 else user_data_copy["password"]
        logger.info(f"Datos finales a guardar (password truncado): {user_data_copy}")

        # Guardar usuario usando el método save_user
        logger.info("Guardando usuario en la base de datos...")
        result = await run_in_executor(mongo_repo.save_user, user_data)
        
        logger.info(f"Usuario creado exitosamente: {user_data['userName']}")
        return {
            "message": "Usuario creado correctamente",
            "userId": user_data["userID"],  # Usar el userID que ya está en user_data
            "userName": user_data["userName"],
            "email": user_data["email"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al crear usuario: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al crear usuario: {str(e)}")

@app.post("/api/v0/screeningChat")
async def screening_chat(request: Request, current_user: dict = Depends(get_current_user)):
    """Endpoint para generar casos de prueba"""
    try:
        input_data = await request.json()
        logger.info(f"Iniciando la generación de casos de prueba para usuario: {current_user.get('username')}")
        
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
async def get_conversations(user_id: str, current_user: dict = Depends(get_current_user)):
    """Obtener conversaciones filtradas por ID de usuario"""
    try:
        # Verificar que el usuario puede acceder a sus propias conversaciones
        if current_user.get('sub') != user_id:
            raise HTTPException(status_code=403, detail="No autorizado para acceder a estas conversaciones")
        
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
async def get_conversation_by_id(conversation_id: str, current_user: dict = Depends(get_current_user)):
    """Obtener una conversación por su ID"""
    try:
        conversation = await run_in_executor(mongo_repo.get_conversation_by_id, conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversación no encontrada")
        
        # Verificar que el usuario puede acceder a esta conversación
        # Asumiendo que la conversación tiene un campo 'userId' o similar
        if conversation.get('userId') != current_user.get('sub'):
            raise HTTPException(status_code=403, detail="No autorizado para acceder a esta conversación")
        
        return conversation
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_all_conversations/{user_id}")
async def get_all_conversations(user_id: str, current_user: dict = Depends(get_current_user)):
    """Obtener todas las conversaciones de un usuario"""
    try:
        # Verificar autorización
        if current_user.get('sub') != user_id:
            raise HTTPException(status_code=403, detail="No autorizado")
        
        conversations = await run_in_executor(mongo_repo.get_all_conversations, user_id)
        return {"conversations": conversations}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v0/deleteConversation/{conversation_id}")
async def delete_conversation(conversation_id: str, current_user: dict = Depends(get_current_user)):
    """Eliminar una conversación por su ID"""
    try:
        # Verificar que la conversación pertenece al usuario
        conversation = await run_in_executor(mongo_repo.get_conversation_by_id, conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversación no encontrada")
        
        if conversation.get('userId') != current_user.get('sub'):
            raise HTTPException(status_code=403, detail="No autorizado para eliminar esta conversación")
        
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
async def delete_history(user_id: str, current_user: dict = Depends(get_current_user)):
    """Eliminar todas las conversaciones de un usuario"""
    try:
        # Verificar autorización
        if current_user.get('sub') != user_id:
            raise HTTPException(status_code=403, detail="No autorizado")
        
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

@app.get("/api/v0/getAllUsers")
async def get_all_users(current_user: dict = Depends(get_current_user)):
    """Obtener todos los usuarios (solo admin)"""
    try:
        # Aquí puedes agregar lógica para verificar si es admin
        # Por ejemplo: if current_user.get('role') != 'admin': raise HTTPException(403)
        
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
async def delete_all_users(current_user: dict = Depends(get_current_user)):
    """Eliminar todos los usuarios (solo admin)"""
    try:
        # Verificar permisos de admin
        # if current_user.get('role') != 'admin': raise HTTPException(403)
        
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
async def get_capability_by_id(capability_id: str, current_user: dict = Depends(get_current_user)):
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
async def get_all_capabilities(current_user: dict = Depends(get_current_user)):
    """Obtener todas las capacidades"""
    try:
        capabilities = await run_in_executor(mongo_repo.get_all_capabilities)
        return {"capabilities": capabilities}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v0/deleteCapabilities")
async def delete_all_capabilities(current_user: dict = Depends(get_current_user)):
    """Eliminar todas las capacidades (solo admin)"""
    try:
        # Verificar permisos de admin
        # if current_user.get('role') != 'admin': raise HTTPException(403)
        
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
async def get_capabilities(conversation_id: str, current_user: dict = Depends(get_current_user)):
    """Obtener capacidades por ID de conversación"""
    try:
        # Verificar que el usuario puede acceder a esta conversación
        conversation = await run_in_executor(mongo_repo.get_conversation_by_id, conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversación no encontrada")
        
        if conversation.get('userId') != current_user.get('sub'):
            raise HTTPException(status_code=403, detail="No autorizado")
        
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

# Endpoint para verificar token (útil para el frontend)
@app.get("/api/v0/auth/verify")
async def verify_token(current_user: dict = Depends(get_current_user)):
    """Verificar si el token es válido"""
    return {
        "valid": True,
        "user": {
            "username": current_user.get('username'),
            "email": current_user.get('email'),
            "user_id": current_user.get('sub')
        }
    }

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