from abc import ABC, abstractmethod
from typing import List

class ChromaDbRepositoryPort(ABC):
    @abstractmethod
    def process_document(self, text: str):
        pass

    @abstractmethod
    def similarity_search(self, query: str, k: int) -> List[str]:
        pass