from __future__ import annotations
from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
import uuid

CapabilityType = Literal["Indispensable", "Deseable"]
SkillStatus = Literal["Cumple", "No Cumple", "No Verificable"]


class SkillEvaluation(BaseModel):
    name: str = Field(..., description="Nombre de la tecnología o habilidad técnica")
    type: CapabilityType = Field(default="Indispensable", description="Indispensable o Deseable")
    level: str = Field(default="Conocimiento", description="Nivel esperado o detectado (Básico, Intermedio, Avanzado, Conocimiento)")
    status: SkillStatus = Field(default="Cumple", description="Cumple, No Cumple o No Verificable")
    evidence: Optional[str] = Field(default=None, description="Cita textual o extracto del CV que justifica el estado")


class TechnicalCategory(BaseModel):
    category: str = Field(..., description="Categoría de habilidades, p. ej. backend, cloud, baseDeDatos")
    skills: List[SkillEvaluation] = Field(default_factory=list)


class CandidatePersonalInfo(BaseModel):
    name: str = Field(default="Candidato no especificado")
    position: str = Field(default="Perfil Técnico")
    client: Optional[str] = ""
    experienceYears: float = Field(default=0.0)
    email: Optional[str] = None
    phone: Optional[str] = None


class EvaluationSummary(BaseModel):
    requiredSkillsMet: int = Field(default=0, alias="cumpleIndispensable")
    optionalSkillsMet: int = Field(default=0, alias="cumpleDeseable")
    totalRequiredSkills: int = Field(default=0)
    totalOptionalSkills: int = Field(default=0)
    matchPercentage: int = Field(default=0)
    recommendation: str = Field(default="")
    additionalNotes: Optional[str] = ""

    model_config = ConfigDict(populate_by_name=True)


class CandidateMatch(BaseModel):
    candidateId: str
    name: str
    position: str
    experienceYears: float
    matchedSkills: List[str] = Field(default_factory=list)
    missingSkills: List[str] = Field(default_factory=list)
    score: float = 0.0
    summary: str = ""
    fileUrl: Optional[str] = None


class TechnicalReport(BaseModel):
    personalInfo: CandidatePersonalInfo
    technicalCapabilities: List[TechnicalCategory]
    evaluationSummary: EvaluationSummary
    resumen: Optional[Dict[str, Any]] = None  # Compatible con v0 legacy
    isGrounded: bool = True
    judgeFeedback: Optional[str] = None
    requiresHumanReview: bool = False
    relevantProfilesFromPool: List[CandidateMatch] = Field(default_factory=list)


class JobPost(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "Puesto Técnico"
    description: str = ""
    requiredCapabilities: List[Dict[str, Any]] = Field(default_factory=list)
    rawText: str = ""
    createdAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CandidateProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recruiterId: str
    personalInfo: CandidatePersonalInfo
    skills: List[str] = Field(default_factory=list)
    summary: str = ""
    rawCvText: str = ""
    fileUrl: Optional[str] = None
    embedding: Optional[List[float]] = None
    createdAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ttl: Optional[int] = None  # Cosmos DB TTL para políticas de retención


class JudgeVerdict(BaseModel):
    approved: bool = Field(..., description="True si todas las afirmaciones están fundamentadas en el CV")
    issues: List[str] = Field(default_factory=list, description="Lista de discrepancias o alucinaciones detectadas")
    reasoning: str = Field(default="", description="Explicación del veredicto del juez")
    confidenceScore: float = Field(default=1.0, description="Puntaje de confianza de 0 a 1")


class User(BaseModel):
    id: str
    email: str
    name: str
    role: str = "recruiter"
    isActive: bool = True
    createdAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Thread(BaseModel):
    id: str
    userId: str
    nameHistory: Optional[str] = None
    processPhase: str = "request_requirements"
    createdAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updatedAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class FileMetadata(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ownerId: str
    fileName: str
    fileType: str
    fileSize: int
    fileUrl: str
    extractedText: str
    createdAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
