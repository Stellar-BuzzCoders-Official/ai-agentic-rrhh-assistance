from abc import ABC, abstractmethod

class GraphQLPort(ABC):
    @abstractmethod
    def execute_query(self, query, variables):
        raise NotImplementedError("Debe implementarse en el adaptador.")
