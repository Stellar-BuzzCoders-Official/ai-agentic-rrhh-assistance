from abc import ABC, abstractmethod

class CountTokensPort(ABC):
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        pass
