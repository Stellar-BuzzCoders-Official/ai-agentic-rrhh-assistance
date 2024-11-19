import fitz  # PyMuPDF
from PIL import Image

class PdfToImageAdapter:
    def __init__(self, file_path):
        self.file_path = file_path

    def convert_to_image(self):
        pdf_document = fitz.open(self.file_path)
        images = []

        for page_number in range(len(pdf_document)):
            page = pdf_document.load_page(page_number)
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)

        return images