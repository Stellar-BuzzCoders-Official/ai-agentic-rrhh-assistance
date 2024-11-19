import nltk
from src.ports.test_cases_ports.count_tokens_port import CountTokensPort

class CountTokensAdapter(CountTokensPort):
    def __init__(self):
        # Descargar el tokenizador de NLTK para español
        nltk.download('punkt_tab')

    def count_tokens(self, text: str) -> int:
        # Tokenizar el texto usando NLTK
        tokens = nltk.word_tokenize(text, language='spanish')
        # Contar los tokens
        return len(tokens)
