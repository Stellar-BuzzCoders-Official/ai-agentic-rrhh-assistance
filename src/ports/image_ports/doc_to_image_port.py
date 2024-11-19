from abc import ABC, abstractmethod

class DocToImagePort(ABC):
    @abstractmethod
    def convert_to_image(self):
        pass
