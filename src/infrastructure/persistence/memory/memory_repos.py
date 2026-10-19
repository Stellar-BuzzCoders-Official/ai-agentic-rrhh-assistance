import math
import logging
from typing import Optional, List, Dict
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from src.application.ports.outbound import (
    CandidateRepositoryPort,
    ThreadRepositoryPort,
    UserRepositoryPort,
    FileRepositoryPort,
    CheckpointerProviderPort,
)
from src.domain.entities import (
    CandidateProfile,
    CandidateMatch,
    Thread,
    User,
    FileMetadata,
)

logger = logging.getLogger(__name__)


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class MemoryCandidateRepository(CandidateRepositoryPort):
    def __init__(self):
        # Clave: (recruiter_id, candidate_id)
        self._candidates: Dict[tuple[str, str], CandidateProfile] = {}

    async def save_candidate(self, candidate: CandidateProfile) -> CandidateProfile:
        key = (candidate.recruiterId, candidate.id)
        self._candidates[key] = candidate
        logger.info("Candidato guardado en memoria: %s (reclutador: %s)", candidate.personalInfo.name, candidate.recruiterId)
        return candidate

    async def get_candidate(self, candidate_id: str, recruiter_id: str) -> Optional[CandidateProfile]:
        return self._candidates.get((recruiter_id, candidate_id))

    async def search_candidates(
        self,
        recruiter_id: str,
        query_text: str,
        query_embedding: Optional[List[float]] = None,
        limit: int = 5,
    ) -> List[CandidateMatch]:
        query_terms = set(query_text.lower().split())
        matches: List[tuple[float, CandidateProfile]] = []

        for (r_id, _), candidate in self._candidates.items():
            if r_id != recruiter_id:
                continue

            score = 0.0
            if query_embedding and candidate.embedding:
                score = _cosine_similarity(query_embedding, candidate.embedding)
            else:
                # Simulación de relevancia por overlap de texto / skills
                cand_terms = set(candidate.rawCvText.lower().split()) | {s.lower() for s in candidate.skills}
                overlap = len(query_terms.intersection(cand_terms))
                score = overlap / max(len(query_terms), 1)

            matches.append((score, candidate))

        # Ordenar descendente por score
        matches.sort(key=lambda x: x[0], reverse=True)
        top = matches[:limit]

        results = []
        for score, cand in top:
            matched_skills = [s for s in cand.skills if s.lower() in query_text.lower()]
            results.append(
                CandidateMatch(
                    candidateId=cand.id,
                    name=cand.personalInfo.name,
                    position=cand.personalInfo.position,
                    experienceYears=cand.personalInfo.experienceYears,
                    matchedSkills=matched_skills or cand.skills[:3],
                    missingSkills=[],
                    score=round(score, 3),
                    summary=cand.summary or cand.personalInfo.position,
                    fileUrl=cand.fileUrl,
                )
            )
        return results

    async def delete_candidate(self, candidate_id: str, recruiter_id: str) -> bool:
        key = (recruiter_id, candidate_id)
        if key in self._candidates:
            del self._candidates[key]
            return True
        return False


class MemoryThreadRepository(ThreadRepositoryPort):
    def __init__(self):
        self._threads: Dict[str, Thread] = {}

    async def save_thread(self, thread: Thread) -> Thread:
        self._threads[thread.id] = thread
        return thread

    async def get_thread(self, thread_id: str) -> Optional[Thread]:
        return self._threads.get(thread_id)

    async def list_threads_by_user(self, user_id: str) -> List[Thread]:
        user_threads = [t for t in self._threads.values() if t.userId == user_id]
        user_threads.sort(key=lambda t: t.updatedAt, reverse=True)
        return user_threads

    async def delete_thread(self, thread_id: str) -> bool:
        if thread_id in self._threads:
            del self._threads[thread_id]
            return True
        return False


class MemoryUserRepository(UserRepositoryPort):
    def __init__(self):
        self._users_by_id: Dict[str, User] = {}
        self._users_by_email: Dict[str, User] = {}

    async def save_user(self, user: User) -> User:
        self._users_by_id[user.id] = user
        self._users_by_email[user.email.lower()] = user
        return user

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        return self._users_by_id.get(user_id)

    async def get_user_by_email(self, email: str) -> Optional[User]:
        return self._users_by_email.get(email.lower())


class MemoryFileRepository(FileRepositoryPort):
    def __init__(self):
        self._files: Dict[str, FileMetadata] = {}

    async def save_file_metadata(self, metadata: FileMetadata) -> FileMetadata:
        self._files[metadata.id] = metadata
        return metadata

    async def get_file_metadata(self, file_id: str) -> Optional[FileMetadata]:
        return self._files.get(file_id)


class MemoryCheckpointerProvider(CheckpointerProviderPort):
    def __init__(self):
        self._saver = MemorySaver()

    def get_checkpointer(self) -> BaseCheckpointSaver:
        return self._saver
