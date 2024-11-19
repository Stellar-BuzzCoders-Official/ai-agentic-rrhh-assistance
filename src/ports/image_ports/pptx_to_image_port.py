from abc import ABC, abstractmethod

class PptxToImagePort(ABC):
    @abstractmethod
    def convert_to_image(self):
        pass
