import pytest
from src.domain.entities import CandidateProfile, CandidatePersonalInfo, Thread, User, FileMetadata
from src.infrastructure.persistence.memory.memory_repos import (
    MemoryCandidateRepository,
    MemoryThreadRepository,
    MemoryUserRepository,
    MemoryFileRepository,
    MemoryCheckpointerProvider,
)


@pytest.mark.asyncio
async def test_memory_repositories():
    cand_repo = MemoryCandidateRepository()
    thread_repo = MemoryThreadRepository()
    user_repo = MemoryUserRepository()
    file_repo = MemoryFileRepository()
    checkpointer_prov = MemoryCheckpointerProvider()

    recruiter_id = "recruiter-123"

    # 1. Guardar y buscar candidato
    cand = CandidateProfile(
        id="cand-1",
        recruiterId=recruiter_id,
        personalInfo=CandidatePersonalInfo(name="Ana Gomez", position="Fullstack Engineer", experienceYears=4.5),
        skills=["Python", "FastAPI", "React", "Docker"],
        summary="Desarrolladora Fullstack con experiencia en Python y React",
        rawCvText="Experiencia sólida en Python, FastAPI, Docker y React.",
        embedding=[0.1] * 10,
    )
    await cand_repo.save_candidate(cand)

    retrieved = await cand_repo.get_candidate("cand-1", recruiter_id)
    assert retrieved is not None
    assert retrieved.personalInfo.name == "Ana Gomez"

    # Búsqueda
    matches = await cand_repo.search_candidates(
        recruiter_id=recruiter_id,
        query_text="Requerimos Python y Docker",
        query_embedding=[0.1] * 10,
        limit=5
    )
    assert len(matches) == 1
    assert matches[0].name == "Ana Gomez"
    assert "Python" in matches[0].matchedSkills

    # 2. Threads
    th = Thread(id="th-1", userId=recruiter_id, nameHistory="Desarrollador Python")
    await thread_repo.save_thread(th)
    user_threads = await thread_repo.list_threads_by_user(recruiter_id)
    assert len(user_threads) == 1
    assert user_threads[0].id == "th-1"

    # 3. Users
    user = User(id=recruiter_id, email="recruiter@joyit.ai", name="Recruiter Test")
    await user_repo.save_user(user)
    found_user = await user_repo.get_user_by_email("recruiter@joyit.ai")
    assert found_user is not None
    assert found_user.id == recruiter_id

    # 4. Files
    f_meta = FileMetadata(
        id="file-1",
        ownerId=recruiter_id,
        fileName="cv_ana.pdf",
        fileType="pdf",
        fileSize=1024,
        fileUrl="https://mock/cv_ana.pdf",
        extractedText="Texto extraido del CV de Ana",
    )
    await file_repo.save_file_metadata(f_meta)
    found_file = await file_repo.get_file_metadata("file-1")
    assert found_file is not None
    assert found_file.fileName == "cv_ana.pdf"

    # 5. Checkpointer
    saver = checkpointer_prov.get_checkpointer()
    assert saver is not None
