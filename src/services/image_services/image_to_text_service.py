import pytesseract
from PIL import Image

class ImageToTextService:
    def convert_image_to_text(self, images):
        text_output = []
        for image in images:
            text = pytesseract.image_to_string(image)
            text_output.append(text)
        return text_output
