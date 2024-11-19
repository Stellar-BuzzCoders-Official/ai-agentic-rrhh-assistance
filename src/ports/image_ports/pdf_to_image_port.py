from abc import ABC, abstractmethod

class PdfToImagePort(ABC):
    @abstractmethod
    def convert_to_image(self):
        pass
