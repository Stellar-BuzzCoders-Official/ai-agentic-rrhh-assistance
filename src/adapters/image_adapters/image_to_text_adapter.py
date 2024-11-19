import pytesseract
from PIL import Image

class ImageToTextAdapter:
    def __init__(self, image_path):
        self.image_path = image_path

    def convert_image_to_text(self):
        try:
            image = Image.open(self.image_path)
            text = pytesseract.image_to_string(image)
            return text
        except Exception as e:
            print(f"An error occurred: {e}")
            return None
