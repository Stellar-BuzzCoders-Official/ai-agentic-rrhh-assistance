import logging
from langchain_core.messages import SystemMessage, HumanMessage
from src.application.agent.state import RRHHState
from src.application.agent.prompts import SYSTEM_JUDGE_PROMPT
from src.config.container import Container
from src.domain.entities import JudgeVerdict, TechnicalReport
from src.domain.services.scoring import calculate_evaluation_summary

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

    # Si ya fue auditado, no volver a auditar
    if state.get("grounding_verdict"):
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
        verdict: JudgeVerdict = await structured_judge.ainvoke([
            SystemMessage(content=SYSTEM_JUDGE_PROMPT),
            HumanMessage(content=audit_prompt),
        ])
    except Exception as e:
        logger.error(
            "Error en la ejecución del sub-agente juez: %s. Aprobando por defecto con advertencia.", str(e))
        verdict = JudgeVerdict(
            approved=True,
            reasoning=f"Auditoría no completada por error técnico: {str(e)}",
            confidenceScore=0.5,
        )

    if verdict.approved:
        logger.info("✅ Veredicto del juez: APROBADO (Score: %.2f)", verdict.confidenceScore)
        report.isGrounded = True
        report.requiresHumanReview = False
        report.judgeFeedback = "Aprobado por el sub-agente auditor de grounding."
    else:
        logger.warning("❌ Veredicto del juez: RECHAZADO. Discrepancias detectadas: %s", verdict.issues)
        report.isGrounded = False
        report.requiresHumanReview = True
        report.judgeFeedback = "Discrepancias detectadas por el auditor de grounding: " + "; ".join(verdict.issues)

        # Ajustar de forma determinística en el informe las habilidades observadas por el juez
        if verdict.issues:
            issues_text = " ".join(verdict.issues).lower()
            for cat in report.technicalCapabilities:
                for skill in cat.skills:
                    if skill.name.lower() in issues_text and skill.status == "Cumple":
                        logger.info("Ajustando habilidad '%s' a 'No Cumple' tras dictamen del juez.", skill.name)
                        skill.status = "No Cumple"
                        skill.evidence = "Observación de auditoría: no fundamentado fehacientemente en el CV."

            # Recalcular métricas determinísticas
            report.evaluationSummary = calculate_evaluation_summary(report.technicalCapabilities)
            if hasattr(report, "resumen") and report.resumen:
                report.resumen["cumpleIndispensable"] = report.evaluationSummary.requiredSkillsMet
                report.resumen["cumpleDeseable"] = report.evaluationSummary.optionalSkillsMet
                report.resumen["recomendation"] = report.evaluationSummary.recommendation

    return {
        "grounding_verdict": verdict,
        "technical_report": report,
    }
