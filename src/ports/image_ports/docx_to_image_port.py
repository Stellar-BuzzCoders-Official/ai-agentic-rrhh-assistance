from abc import ABC, abstractmethod

class DocxToImagePort(ABC):
    @abstractmethod
    def convert_to_image(self):
        pass
