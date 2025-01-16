from flask import Flask, request, jsonify
import ollama as ollama
from flask_cors import CORS
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

load_dotenv()

app = Flask(__name__)
CORS(app)
app.config['DEBUG'] = True
logger = logging.getLogger(__name__)

mongo_repo = MongoDBRepository()

FLAGGER_MODEL = os.getenv('FLAGGER_MODEL')

# Instanciar el LLM basado en FLAGGER_MODEL
if FLAGGER_MODEL == 'azureml':
    llm = AzureRepository()
    logger.info("Usando AzureML como proveedor de LLM.")
elif FLAGGER_MODEL == 'ollama':
    # Usar OllamaRepository
    llm = OllamaRepository()
    logger.info("Usando Ollama como proveedor de LLM.")
elif FLAGGER_MODEL == 'geminilm':
    llm = GeminiRepository()
    logger.info("Usando GeminiLM como proveedor de LLM.")
else:
    raise ValueError(f"El modelo FLAGGER_MODEL '{FLAGGER_MODEL}' no es soportado.")

count_tokens = CountTokensAdapter()
conversation_manager = ConversationManagementAdapter(mongo_repo)
name_history_generator = NameHistoryGeneratorAdapter(llm)
prompt_generator = TestCasePromptGeneratorAdapter(llm)
process_request_requirements = ProcessRequestRequirementsAdapter(llm, mongo_repo, name_history_generator, conversation_manager, count_tokens)
process_request_cv = ProcessCvAdapter(llm, mongo_repo, prompt_generator, conversation_manager, count_tokens)
test_case_generator_service = TechnicalReportGeneratorService(process_request_requirements, process_request_cv)
api_controller = APIController(test_case_generator_service)

@app.route('/')
def index():
    return jsonify({"message": "Bienvenido a la API de Screening."})

@app.route('/api/v0/screeningChat', methods=['POST'])
def test_generate_cases():
    input_data = request.get_json()
    app.logger.debug(f"Datos recibidos: {input_data}")
    try:
        app.logger.info("Iniciando la generación de casos de prueba.")
        response, status_code = api_controller.generate_test_cases(input_data)
        app.logger.debug(f"Respuesta generada: {response}, Código de estado: {status_code}")
        return jsonify(response), status_code
    except ValueError as e:
        app.logger.error(f"Error de valor: {str(e)}")
        return jsonify({"error": str(e)}), 404 
    except Exception as e:
        app.logger.error(f"Error interno: {str(e)}", exc_info=True)  
        return jsonify({"error": "Ocurrió un error interno del servidor."}), 500

@app.route('/api/v0/conversationsIdName/<string:user_ID>', methods=['GET'])
def get_conversations(user_ID):
    try:
        # Verificar si el usuario existe
        user = mongo_repo.get_user_by_id(user_ID)
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404
        conversations = mongo_repo.get_all_conversations(user_ID)
        filtered_conversations = []
        for conversation in conversations:
            filtered_conversation = {
                "_id": str(conversation.get('_id')),
                "nameHistory": conversation.get('data', {}).get('nameHistory')
            }
            filtered_conversations.append(filtered_conversation)

        return jsonify(filtered_conversations)
    except (PyMongoError, Exception) as e:
        return jsonify({"error": f"Error al recuperar las conversaciones: {str(e)}"}), 500


@app.route('/api/v0/getConversation//<conversation_id>', methods=['GET'])
def get_conversation_by_id(conversation_id):
    """
    Endpoint para obtener un conversaciones por su ID.
    """
    try:
        conversation = mongo_repo.get_conversation_by_id(conversation_id)
        if conversation:
            return jsonify(conversation), 200
        else:
            return jsonify({"error": "conversaciones no encontrado"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_all_conversations/<user_id>', methods=['GET'])
def get_all_conversations(user_id):
    try:
        conversations = mongo_repo.get_all_conversations(user_id)
        return jsonify({"conversations": conversations}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v0/deleteConversation/<conversation_id>', methods=['DELETE'])
def update_conversation_user_story(conversation_id):
    """Elimina un conversaciones de MongoDB por su UUID."""
    try:
        result = mongo_repo.delete_conversation(conversation_id)
        if result.deleted_count == 0:
            return jsonify({"conversation": f"El conversaciones con _id {conversation_id} no fue encontrado."}), 404
        return jsonify({"conversation": f"El conversaciones con _id {conversation_id} ha sido eliminado."}), 200
    except (PyMongoError, Exception) as e:
        return jsonify({"error": f"Error al eliminar la conversacion: {str(e)}"}), 500
    
@app.route('/api/v0/deleteHistoryConversations/<string:user_ID>', methods=['DELETE'])
def delete_history(user_ID):
    """Elimina todas las conversaciones de la colección para un usuario específico."""
    try:
        user = mongo_repo.get_user_by_id(user_ID)
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

        response, status_code = mongo_repo.delete_history_conversation(user_ID)
        return jsonify(response), status_code
    except (PyMongoError, Exception) as e:
        return jsonify({"error": f"Error al eliminar el historial de conversaciones: {str(e)}"}), 500

@app.route('/api/v0/createUser', methods=['POST'])
def create_user():
    try:
        user_data = request.json
        if not user_data:
            return jsonify({"error": "Datos del usuario no proporcionados"}), 400
        result = mongo_repo.save_user(user_data)
        if result and isinstance(result, str):
            return jsonify({
                "message": "Usuario creado correctamente",
                "userId": result
            }), 201
        else:
            logger.error("Se creo correctamente")
            return jsonify({"error": "Se creo correctamente"}), 200

    except Exception as e:
        logger.error(f"Error al crear usuario: {str(e)}")
        return jsonify({"error": f"Error al crear usuario: {str(e)}"}), 500
    
@app.route('/api/v0/getAllUsers', methods=['GET'])
def get_all_users():
    try:
        users = mongo_repo.get_all_users()
        
        if users:
            return jsonify({"users": users}), 200
        else:
            return jsonify({"message": "No users found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v0/deleteUsers', methods=['DELETE'])
def delete_all_users():
    try:
        deleted_count = mongo_repo.delete_all_users()
        return jsonify({
            "message": f"Se han borrado {deleted_count} usuarios exitosamente.",
            "deleted_count": deleted_count
        }), 200
    except Exception as e:
        return jsonify({
            "error": "Ha ocurrido un error al intentar borrar todos los usuarios.",
            "details": str(e)
        }), 500
        
@app.route('/api/v0/getCapability/<string:capability_id>', methods=['GET'])
def get_capability_by_id(capability_id):
    try:
        capability = mongo_repo.get_capability_by_id(capability_id)
        if capability:
            return jsonify(capability), 200
        else:
            return jsonify({"error": "Capacidad no encontrada"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v0/getCapabilities', methods=['GET'])
def get_all_capabilities():
    try:
        capabilities = mongo_repo.get_all_capabilities()
        return jsonify({"capabilities": capabilities}), 200
    except Exception as e:
                return jsonify({"error": str(e)}), 500

@app.route('/api/v0/deleteCapabilities', methods=['DELETE'])
def delete_all_capabilities():
    try:
        deleted_count = mongo_repo.delete_all_capabilities()
        return jsonify({
            "message": f"Se han borrado {deleted_count} capacidades exitosamente.",
            "deleted_count": deleted_count
        }), 200
    except Exception as e:
        return jsonify({
            "error": "Ha ocurrido un error al intentar borrar todas las capacidades.",
            "details": str(e)
        }), 500
        
@app.route('/api/v0/capabilities/<string:conversation_id>', methods=['GET'])
def get_capabilities(conversation_id: str):
    try:
        # Llamar al servicio para obtener las capacidades
        capabilities = mongo_repo.get_capabilities_by_conversation_id(conversation_id)

        # Si no se encuentran capacidades, devolver un error 404
        if not capabilities:
            return jsonify({"message": "No se encontraron capacidades para la conversación solicitada."}), 404
        
        # Devolver las capacidades como una respuesta JSON
        return jsonify(capabilities), 200
    
    except Exception as e:
        return jsonify({"message": f"Error al obtener capacidades: {str(e)}"}), 500

if __name__ == '__main__':
    print("Iniciando la aplicación Flask en modo depuración...")
    app.run(host='0.0.0.0', port=5000, debug=True)
