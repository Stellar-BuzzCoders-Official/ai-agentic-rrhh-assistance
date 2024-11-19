from src.adapters.image_adapters.docx_to_image_adapter import DocxToImageAdapter
from src.adapters.image_adapters.pdf_to_image_adapter import PdfToImageAdapter
from src.adapters.image_adapters.pptx_to_image_adapter import PptxToImageAdapter
from src.adapters.image_adapters.doc_to_image_adapter import DocToImageAdapter
from src.adapters.image_adapters.ppt_to_image_adapter import PptToImageAdapter

class ToImageService:
    def __init__(self):
        self.adapters = {
            'docx': DocxToImageAdapter,
            'pdf': PdfToImageAdapter,
            'pptx': PptxToImageAdapter,
            'doc': DocToImageAdapter,
            'ppt': PptToImageAdapter,
        }

    def convert_document_to_image(self, file_path, file_type):
        adapter_class = self.adapters.get(file_type.lower())
        if adapter_class:
            adapter = adapter_class(file_path)
            return adapter.convert_to_image()
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
