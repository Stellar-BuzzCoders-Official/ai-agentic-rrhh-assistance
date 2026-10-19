from typing import List
from src.domain.entities import TechnicalCategory, EvaluationSummary


def calculate_evaluation_summary(categories: List[TechnicalCategory], additional_notes: str = "") -> EvaluationSummary:
    """
    Calcula de forma 100% determinística y verificable las métricas de cumplimiento
    del candidato a partir de sus habilidades evaluadas.
    """
    cumple_indispensable = 0
    total_indispensable = 0
    cumple_deseable = 0
    total_deseable = 0

    for category in categories:
        for skill in category.skills:
            if skill.type == "Indispensable":
                total_indispensable += 1
                if skill.status == "Cumple":
                    cumple_indispensable += 1
            elif skill.type == "Deseable":
                total_deseable += 1
                if skill.status == "Cumple":
                    cumple_deseable += 1

    total_requisitos = total_indispensable + total_deseable
    total_cumplidos = cumple_indispensable + cumple_deseable

    if total_requisitos > 0:
        match_percentage = round((total_cumplidos / total_requisitos) * 100)
    else:
        match_percentage = 0

    recommendation = f"Este candidato cumple en un {match_percentage}% los requerimientos para el puesto"

    return EvaluationSummary(
        requiredSkillsMet=cumple_indispensable,
        optionalSkillsMet=cumple_deseable,
        totalRequiredSkills=total_indispensable,
        totalOptionalSkills=total_deseable,
        matchPercentage=match_percentage,
        recommendation=recommendation,
        additionalNotes=additional_notes or "Evaluación técnica automatizada con verificación de evidencia."
    )
