from PIL import Image, ImageDraw
import docx

class DocToImageAdapter:
    def __init__(self, file_path):
        self.file_path = file_path

    def convert_to_image(self):
        doc = docx.Document(self.file_path)
        images = []
        
        for para in doc.paragraphs:
            img = Image.new('RGB', (500, 100), color = (255, 255, 255))
            d = ImageDraw.Draw(img)
            d.text((10, 10), para.text, fill=(0, 0, 0))
            images.append(img)

        return images
