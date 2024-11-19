from abc import ABC, abstractmethod

class RequestResponsePort(ABC):
    @abstractmethod
    def process_request(self, request):
        raise NotImplementedError("Debe implementarse en el adaptador.")

    @abstractmethod
    def format_response(self, data, status_code=200):
        raise NotImplementedError("Debe implementarse en el adaptador.")
