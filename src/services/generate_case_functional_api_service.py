from adapters.api_adapters import SwaggerAdapter, GraphQLAdapter, RequestResponseAdapter

class ApiProcessingService:
    def __init__(self, swagger_adapter: SwaggerAdapter, graphql_adapter: GraphQLAdapter, request_response_adapter: RequestResponseAdapter):
        self.swagger_adapter = swagger_adapter
        self.graphql_adapter = graphql_adapter
        self.request_response_adapter = request_response_adapter
    
    def generate_swagger_docs(self):
        
        return self.swagger_adapter.generate_docs()

    def handle_graphql_request(self, query, variables):
        return self.graphql_adapter.execute_query(query, variables)

    def process_http_request(self, request):
        request_data = self.request_response_adapter.process_request(request)
        response = self.request_response_adapter.format_response(request_data)
        return response

    def process_for_llm(self, request_data):
        
        prompt = f"Genera un caso de uso a partir de esta solicitud: {request_data}"
        
        return prompt