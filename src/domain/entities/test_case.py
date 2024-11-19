from typing import List

class TestCase:
    def __init__(self, description: str, validators: List[str], estimation: str, priority: str):
        self.description = description
        self.validators = validators
        self.estimation = estimation
        self.priority = priority