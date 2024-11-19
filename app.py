from flask import Flask, request, jsonify
import ollama as ollama
from flask_cors import CORS
from src.adapters.input_adapters import APIController
from src.services import TestCaseGeneratorService
from src.adapters.output_adapters import ChromaRepository
from src.adapters.output_adapters import OllamaRepository
from src.adapters.output_adapters import MongoDBRepository
from src.adapters.test_cases_adapters import ProcessContextAdapter
from src.adapters.test_cases_adapters.process_context_api_adapter import ProcessContextApiAdapter
from src.adapters.test_cases_adapters import ProcessUserStoryAdapter
from src.adapters.test_cases_adapters.test_case_prompt_generator_adapter import TestCasePromptGeneratorAdapter
from src.adapters.conversation_adapters.name_history_generator_adapter import NameHistoryGeneratorAdapter
from src.adapters.conversation_adapters.conversation_management_adapter import ConversationManagementAdapter
from src.adapters.test_cases_adapters.process_user_story_api_adapter import ProcessUserStoryApiAdapter
from src.adapters.test_cases_adapters.test_case_prompt_generator_api_adapter import TestCasePromptGeneratorApiAdapter
import logging
from src.adapters.test_cases_adapters.count_tokens_adapter import CountTokensAdapter
from pymongo.errors import PyMongoError

app = Flask(__name__)
CORS(app)
app.config['DEBUG'] = True
logger = logging.getLogger(__name__)

mongo_repo = MongoDBRepository()
llm = OllamaRepository()
count_tokens = CountTokensAdapter()
conversation_manager = ConversationManagementAdapter(mongo_repo)
name_history_generator = NameHistoryGeneratorAdapter(llm)
prompt_generator = TestCasePromptGeneratorAdapter(llm)
prompt_generator_api = TestCasePromptGeneratorApiAdapter(llm)
process_context = ProcessContextAdapter(llm, mongo_repo, name_history_generator, conversation_manager, count_tokens)
process_context_api = ProcessContextApiAdapter(llm, mongo_repo, name_history_generator, conversation_manager, count_tokens)
process_user_story = ProcessUserStoryAdapter(llm, mongo_repo, prompt_generator, conversation_manager, count_tokens)
process_user_story_api = ProcessUserStoryApiAdapter(llm, mongo_repo, prompt_generator_api, conversation_manager, count_tokens)
test_case_generator_service = TestCaseGeneratorService(process_context, process_user_story, process_context_api, process_user_story_api)
api_controller = APIController(test_case_generator_service)

@app.route('/')
def index():
    print("Endpoint '/' llamado.")
    return 'Bienvenido a la API de QA Assistant !'

@app.route('/testGenerateCases', methods=['POST'])
def test_generate_cases():
    input_data = request.get_json()

    # Registro de la entrada
    app.logger.debug(f"Datos recibidos: {input_data}")
    
    try:
        app.logger.info("Iniciando la generación de casos de prueba.")
        
        # Llamada al controlador para generar los casos de prueba
        response, status_code = api_controller.generate_test_cases(input_data)
        
        # Registro de la respuesta
        app.logger.debug(f"Respuesta generada: {response}, Código de estado: {status_code}")
        
        return jsonify(response), status_code

    except ValueError as e:
        # Registro de error para ValueError
        app.logger.error(f"Error de valor: {str(e)}")
        return jsonify({"error": str(e)}), 404  # Código 404 para Not Found

    except Exception as e:
        # Registro de error general, con stack trace
        app.logger.error(f"Error interno: {str(e)}", exc_info=True)  # exc_info=True incluye el stack trace
        return jsonify({"error": "Ocurrió un error interno del servidor."}), 500


@app.route('/newChat/', methods=['POST'])
def new_chat():
    """Endpoint para iniciar una nueva conversación y limpiar la caché."""
    data = request.get_json()  
    
    response = api_controller.new_chat(data)
    return jsonify(response)

@app.route('/conversations_id_name/<string:user_ID>', methods=['GET'])
def get_conversations(user_ID):
    try:
        # Verificar si el usuario existe
        user = mongo_repo.get_user_by_id(user_ID)
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

        # Recuperar las conversaciones de MongoDB para el usuario específico
        conversations = mongo_repo.get_all_conversations(user_ID)

        # Filtrar las conversaciones para obtener solo id y nameHistory
        filtered_conversations = []
        for conversation in conversations:
            filtered_conversation = {
                "_id": str(conversation.get('_id')),  # Convertir ObjectId a string
                "nameHistory": conversation.get('data', {}).get('nameHistory')
            }
            filtered_conversations.append(filtered_conversation)

        return jsonify(filtered_conversations)
    except (PyMongoError, Exception) as e:
        return jsonify({"error": f"Error al recuperar las conversaciones: {str(e)}"}), 500


@app.route('/getConversation//<conversation_id>', methods=['GET'])
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

@app.route('/delete_conversation/<conversation_id>', methods=['DELETE'])
def update_conversation_user_story(conversation_id):
    """Elimina un conversaciones de MongoDB por su UUID."""
    try:
        # Usamos el método del repositorio para eliminar un conversaciones por su _id
        result = mongo_repo.delete_conversation(conversation_id)
        if result.deleted_count == 0:
            return jsonify({"conversation": f"El conversaciones con _id {conversation_id} no fue encontrado."}), 404
        return jsonify({"conversation": f"El conversaciones con _id {conversation_id} ha sido eliminado."}), 200
    except (PyMongoError, Exception) as e:
        return jsonify({"error": f"Error al eliminar la conversacion: {str(e)}"}), 500
    
@app.route('/delete_history_conversations/<string:user_ID>', methods=['DELETE'])
def delete_history(user_ID):
    """Elimina todas las conversaciones de la colección para un usuario específico."""
    try:
        # Verificar si el usuario existe
        user = mongo_repo.get_user_by_id(user_ID)
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

        # Llamar al método para eliminar el historial de conversaciones
        response, status_code = mongo_repo.delete_history_conversation(user_ID)
        return jsonify(response), status_code
    except (PyMongoError, Exception) as e:
        return jsonify({"error": f"Error al eliminar el historial de conversaciones: {str(e)}"}), 500

@app.route('/user', methods=['POST'])
def create_user():
    try:
        # Obtener los datos del usuario desde el cuerpo de la solicitud
        user_data = request.json

        # Validar que los datos existan
        if not user_data:
            return jsonify({"error": "Datos del usuario no proporcionados"}), 400

        # Llamar al método para guardar el usuario
        result = mongo_repo.save_user(user_data)

        # Verificar si el usuario se guardó correctamente
        if result and isinstance(result, str):
            # Asumiendo que save_user() devuelve el ID del usuario como string
            return jsonify({
                "message": "Usuario creado correctamente",
                "userId": result
            }), 201
        else:
            # Si no se recibió un ID válido, devolver un error
            logger.error("Se creo correctamente")
            return jsonify({"error": "Se creo correctamente"}), 200

    except Exception as e:
        logger.error(f"Error al crear usuario: {str(e)}")
        return jsonify({"error": f"Error al crear usuario: {str(e)}"}), 500
    
@app.route('/get_all_users', methods=['GET'])
def get_all_users():
    try:
        # Llamar al método get_all_users del repositorio
        users = mongo_repo.get_all_users()
        
        if users:
            return jsonify({"users": users}), 200
        else:
            return jsonify({"message": "No users found"}), 404
    except Exception as e:
        # Manejo de errores y devolver mensaje de error
        return jsonify({"error": str(e)}), 500

@app.route('/delete_users', methods=['DELETE'])
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

if __name__ == '__main__':
    print("Iniciando la aplicación Flask en modo depuración...")
    app.run(host='0.0.0.0', port=5000, debug=True)
