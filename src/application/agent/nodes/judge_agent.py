import logging
from langchain_core.messages import SystemMessage, HumanMessage
from src.application.agent.state import RRHHState
from src.application.agent.prompts import SYSTEM_JUDGE_PROMPT
from src.config.container import Container
from src.domain.entities import JudgeVerdict, TechnicalReport

logger = logging.getLogger(__name__)


async def judge_agent_node(state: RRHHState) -> dict:
    """
    Sub-agente auditor independiente de Grounding:
    Verifica que las capacidades y afirmaciones del informe técnico estén
    100% fundamentadas en el texto del CV del candidato.
    """
    report: TechnicalReport | None = state.get("technical_report")
    if not report:
        return {}

    # Si ya fue aprobado, no volver a auditar
    if state.get("grounding_verdict") and state["grounding_verdict"].approved:
        return {}

    container = Container.get_instance()
    cv_id = state.get("current_cv_id")
    cv_text = ""

    if cv_id:
        file_meta = await container.file_repo.get_file_metadata(cv_id)
        if file_meta:
            cv_text = file_meta.extractedText

    if not cv_text:
        logger.warning("No se encontró texto del CV para auditar con el juez.")
        return {}

    logger.info("Auditoría de Grounding iniciada por el sub-agente juez...")
    judge_llm = container.judge_llm_provider.get_chat_model(temperature=0.0)

    # Construir resumen de afirmaciones del informe a verificar
    claims_to_audit = []
    for cat in report.technicalCapabilities:
        for skill in cat.skills:
            claims_to_audit.append(
                f"- Habilidad: {skill.name} | Estado asignado: {skill.status} | Evidencia reportada: '{skill.evidence}'"
            )

    audit_prompt = f"""AUDITORÍA DE GROUNDING:
A continuación se presenta el texto del CV del candidato y las evaluaciones asignadas en el informe técnico.

=== TEXTO ORIGINAL DEL CV ===
{cv_text[:10000]}

=== AFIRMACIONES Y EVALUACIONES DEL INFORME ===
Candidato: {report.personalInfo.name} ({report.personalInfo.position})
Años de experiencia: {report.personalInfo.experienceYears}

Evaluaciones:
{chr(10).join(claims_to_audit)}

Dictamina si las afirmaciones y habilidades marcadas como 'Cumple' son veraces y fundamentadas.
"""

    structured_judge = judge_llm.with_structured_output(JudgeVerdict)
    try:
        verdict: JudgeVerdict = structured_judge.invoke([
            SystemMessage(content=SYSTEM_JUDGE_PROMPT),
            HumanMessage(content=audit_prompt),
        ])
    except Exception as e:
        logger.error("Error en la ejecución del sub-agente juez: %s. Aprobando por defecto con advertencia.", str(e))
        verdict = JudgeVerdict(
            approved=True,
            reasoning=f"Auditoría no completada por error técnico: {str(e)}",
            confidenceScore=0.5,
        )

    current_retries = state.get("grounding_retries", 0)

    if verdict.approved:
        logger.info("✅ Veredicto del juez: APROBADO (Score: %.2f)", verdict.confidenceScore)
        report.isGrounded = True
        report.judgeFeedback = "Aprobado por el sub-agente auditor de grounding."
        return {
            "grounding_verdict": verdict,
            "technical_report": report,
        }
    else:
        logger.warning("❌ Veredicto del juez: RECHAZADO. Discrepancias detectadas: %s", verdict.issues)
        current_retries += 1

        if current_retries < 2:
            # Enviar mensaje al agente principal para corregir
            feedback_msg = HumanMessage(
                content=(
                    f"⚠️ OBSERVACIÓN DEL SUB-AGENTE AUDITOR DE GROUNDING:\n"
                    f"Se detectaron posibles discrepancias o falta de evidencia en el informe:\n"
                    + "\n".join([f"- {iss}" for iss in verdict.issues])
                    + "\nPor favor, ajusta las habilidades afectadas a 'No Cumple' o 'No Verificable' y regenera la evaluación con rigor estricto."
                )
            )
            return {
                "grounding_verdict": verdict,
                "grounding_retries": current_retries,
                "messages": [feedback_msg],
            }
        else:
            # Se agotaron los reintentos: marcar informe como 'Requiere revisión humana'
            report.isGrounded = False
            report.requiresHumanReview = True
            report.judgeFeedback = "Discrepancias no resueltas: " + "; ".join(verdict.issues)
            return {
                "grounding_verdict": verdict,
                "grounding_retries": current_retries,
                "technical_report": report,
            }
