from abc import ABC, abstractmethod
from src.domain.entities.user_story import UserStory

class APIPort(ABC):
    @abstractmethod
    def generate_test_cases(self, user_story: UserStory) -> str:
        pass