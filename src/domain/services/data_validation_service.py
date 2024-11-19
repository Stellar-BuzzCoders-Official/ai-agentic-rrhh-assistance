import logging

class DataValidationService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def validate_request_data(self, data: dict) -> dict:
        self.logger.info(f"Validando datos de solicitud: {data}")
        
        if 'data' not in data:
            self.logger.error("Falta 'data' en la solicitud")
            return {"error": "Missing 'data' in request"}, 400
        
        test_type = data['data'].get('testType')
        message = data['data'].get('message', [])

        self.logger.debug(f"test_type: {test_type}, message: {message}")

        if not test_type or test_type not in ['context', 'user_story']:
            self.logger.error(f"'testType' inválido o faltante en la solicitud: {test_type}")
            return {"error": "Invalid or missing 'testType' in request"}, 400

        if not message or not isinstance(message, list) or len(message) < 1:
            self.logger.error(f"'message' inválido o faltante en la solicitud: {message}")
            return {"error": "Invalid or missing 'message' in request"}, 400

        content = message[0].get('content', "")
        if not content:
            self.logger.error("El contenido está vacío")
            return {"error": "Content is empty"}, 400

        self.logger.info("Validación de datos de solicitud exitosa.")
        return None
