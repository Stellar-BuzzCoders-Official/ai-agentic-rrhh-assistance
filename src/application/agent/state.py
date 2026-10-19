from typing import Annotated, Optional, List, Dict, Any
from typing_extensions import TypedDict
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from src.domain.entities import (
    JobPost,
    TechnicalReport,
    CandidateMatch,
    JudgeVerdict,
)


class RRHHState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]
    user_id: str  # Recruiter ID
    thread_id: str
    process_phase: str  # 'request_requirements' | 'upload_cv_and_match'
    job_post: Optional[JobPost]
    current_cv_id: Optional[str]
    technical_report: Optional[TechnicalReport]
    relevant_candidates: List[CandidateMatch]
    grounding_verdict: Optional[JudgeVerdict]
    grounding_retries: int
    is_safe: bool
    safety_reason: Optional[str]
    name_history: Optional[str]
    client_response_payload: Optional[Dict[str, Any]]
