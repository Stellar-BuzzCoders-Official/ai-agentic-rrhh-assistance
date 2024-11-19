from abc import ABC, abstractmethod

class ImageToTextPort:
    @abstractmethod
    def convert_to_text(self):
        pass