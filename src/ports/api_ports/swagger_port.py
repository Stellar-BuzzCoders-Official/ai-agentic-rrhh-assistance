from abc import ABC, abstractmethod

class SwaggerPort(ABC):
    @abstractmethod
    def generate_docs(self):
        raise NotImplementedError("Debe implementarse en el adaptador.")
