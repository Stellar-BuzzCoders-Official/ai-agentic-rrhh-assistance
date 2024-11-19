from ports.api_ports.graphQL_port import GraphQLPort

class GraphQLAdapter(GraphQLPort):
    def execute_query(self, query, variables):
        
        return {"data": "resultado de GraphQL"}