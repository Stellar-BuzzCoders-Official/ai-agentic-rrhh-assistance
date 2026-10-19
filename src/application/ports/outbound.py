from abc import ABC, abstractmethod
from typing import Optional, List, Tuple, Any
from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from langgraph.checkpoint.base import BaseCheckpointSaver
from src.domain.entities import (
    CandidateProfile,
    CandidateMatch,
    Thread,
    User,
    FileMetadata,
)


class ChatModelProviderPort(ABC):
    @abstractmethod
    def get_chat_model(self, temperature: float = 0.0) -> BaseChatModel:
        """Retorna una instancia de BaseChatModel configurada"""
        pass


class EmbeddingsProviderPort(ABC):
    @abstractmethod
    def get_embeddings(self) -> Embeddings:
        """Retorna una instancia de Embeddings configurada"""
        pass


class DocumentExtractorPort(ABC):
    @abstractmethod
    async def extract_text(self, file_bytes: bytes, file_name: str, file_type: str) -> str:
        """Extrae texto estructurado de un archivo (PDF, DOCX, etc.)"""
        pass


class FileStoragePort(ABC):
    @abstractmethod
    async def upload_file(self, file_bytes: bytes, file_name: str, file_type: str) -> str:
        """Guarda el archivo y retorna su URL pública o SAS"""
        pass

    @abstractmethod
    async def download_file(self, file_url_or_id: str) -> bytes:
        """Descarga el contenido binario del archivo"""
        pass


class CandidateRepositoryPort(ABC):
    @abstractmethod
    async def save_candidate(self, candidate: CandidateProfile) -> CandidateProfile:
        """Guarda o actualiza un candidato con su embedding en el pool del reclutador"""
        pass

    @abstractmethod
    async def get_candidate(self, candidate_id: str, recruiter_id: str) -> Optional[CandidateProfile]:
        """Recupera un candidato por ID dentro de la partición del reclutador"""
        pass

    @abstractmethod
    async def search_candidates(
        self,
        recruiter_id: str,
        query_text: str,
        query_embedding: Optional[List[float]] = None,
        limit: int = 5,
    ) -> List[CandidateMatch]:
        """Búsqueda híbrida (vector + texto) en el pool del reclutador"""
        pass

    @abstractmethod
    async def delete_candidate(self, candidate_id: str, recruiter_id: str) -> bool:
        """Elimina un candidato del pool"""
        pass


class ThreadRepositoryPort(ABC):
    @abstractmethod
    async def save_thread(self, thread: Thread) -> Thread:
        """Guarda o actualiza los metadatos de un hilo"""
        pass

    @abstractmethod
    async def get_thread(self, thread_id: str) -> Optional[Thread]:
        """Obtiene un hilo por su identificador"""
        pass

    @abstractmethod
    async def list_threads_by_user(self, user_id: str) -> List[Thread]:
        """Obtiene todos los hilos pertenecientes a un usuario"""
        pass

    @abstractmethod
    async def delete_thread(self, thread_id: str) -> bool:
        """Elimina los metadatos de un hilo"""
        pass


class UserRepositoryPort(ABC):
    @abstractmethod
    async def save_user(self, user: User) -> User:
        """Guarda o actualiza un usuario"""
        pass

    @abstractmethod
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Busca un usuario por su identificador único (oid)"""
        pass

    @abstractmethod
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Busca un usuario por correo electrónico"""
        pass


class FileRepositoryPort(ABC):
    @abstractmethod
    async def save_file_metadata(self, metadata: FileMetadata) -> FileMetadata:
        """Registra metadatos y texto extraído de un archivo subido"""
        pass

    @abstractmethod
    async def get_file_metadata(self, file_id: str) -> Optional[FileMetadata]:
        """Recupera metadatos y texto extraído por file_id"""
        pass


class CheckpointerProviderPort(ABC):
    @abstractmethod
    def get_checkpointer(self) -> BaseCheckpointSaver:
        """Retorna el checkpointer configurado para LangGraph"""
        pass


class ContentSafetyPort(ABC):
    @abstractmethod
    async def check_input(self, text: str) -> Tuple[bool, str]:
        """Valida que el texto no contenga inyecciones de prompt o contenido inapropiado"""
        pass


class TokenVerifierPort(ABC):
    @abstractmethod
    async def verify_token(self, token: str) -> User:
        """Valida el token JWT (Entra ID o dev) y retorna el usuario autenticado"""
        pass
