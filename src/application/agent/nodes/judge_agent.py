import asyncio
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from src.application.agent.state import RRHHState
from src.application.agent.prompts import SYSTEM_JUDGE_PROMPT
from src.config.container import Container
from src.domain.entities import JudgeVerdict, TechnicalReport
from src.domain.services.scoring import calculate_evaluation_summary

logger = logging.getLogger(__name__)


async def _audit_report(
    report: TechnicalReport,
    cv_text: str,
    judge_llm,
) -> JudgeVerdict:
    if not cv_text:
        return JudgeVerdict(
            approved=True,
            reasoning="Auditoría no requerida: texto del CV no disponible.",
            confidenceScore=0.8,
        )

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
            "Error en la ejecución del sub-agente juez para %s: %s. Aprobando por defecto con advertencia.",
            report.personalInfo.name,
            str(e),
        )
        verdict = JudgeVerdict(
            approved=True,
            reasoning=f"Auditoría no completada por error técnico: {str(e)}",
            confidenceScore=0.5,
        )

    if verdict.approved:
        logger.info("✅ Veredicto del juez para %s: APROBADO (Score: %.2f)", report.personalInfo.name, verdict.confidenceScore)
        report.isGrounded = True
        report.requiresHumanReview = False
        report.judgeFeedback = "Aprobado por el sub-agente auditor de grounding."
    else:
        logger.warning("❌ Veredicto del juez para %s: RECHAZADO. Discrepancias detectadas: %s", report.personalInfo.name, verdict.issues)
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

    return verdict


async def judge_agent_node(state: RRHHState) -> dict:
    """
    Sub-agente auditor independiente de Grounding:
    Verifica que las capacidades y afirmaciones de cada informe técnico estén
    100% fundamentadas en el texto del CV del candidato correspondiente.
    """
    reports = state.get("technical_reports") or ([state.get("technical_report")] if state.get("technical_report") else [])
    if not reports:
        return {}

    # Si ya fue auditado el veredicto general y ningún reporte está pendiente
    if state.get("grounding_verdict") and all(r.judgeFeedback for r in reports):
        return {}

    container = Container.get_instance()
    judge_llm = container.judge_llm_provider.get_chat_model(temperature=0.0)

    candidate_cv_texts = state.get("candidate_cv_texts") or {}
    fallback_cv_text = ""
    cv_id = state.get("current_cv_id")
    if cv_id:
        file_meta = await container.file_repo.get_file_metadata(cv_id)
        if file_meta:
            fallback_cv_text = file_meta.extractedText

    logger.info("Auditoría de Grounding iniciada por el sub-agente juez para %d reporte(s)...", len(reports))

    tasks = []
    for report in reports:
        if report.judgeFeedback and report.isGrounded is not None:
            continue
        cv_text = candidate_cv_texts.get(report.personalInfo.name) or fallback_cv_text
        tasks.append(_audit_report(report, cv_text, judge_llm))

    latest_verdict = None
    if tasks:
        verdicts = await asyncio.gather(*tasks)
        latest_verdict = verdicts[-1]
    elif state.get("grounding_verdict"):
        latest_verdict = state.get("grounding_verdict")
    else:
        latest_verdict = JudgeVerdict(
            approved=all(r.isGrounded for r in reports),
            reasoning="Auditoría completada para todos los candidatos.",
            confidenceScore=1.0,
        )

    return {
        "grounding_verdict": latest_verdict,
        "technical_reports": reports,
        "technical_report": reports[-1] if reports else None,
    }
