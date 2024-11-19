from abc import ABC, abstractmethod

class PptToImagePort(ABC):
    @abstractmethod
    def convert_to_image(self):
        pass
