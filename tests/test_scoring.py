from src.domain.entities import TechnicalCategory, SkillEvaluation
from src.domain.services.scoring import calculate_evaluation_summary


def test_scoring_calculation():
    categories = [
        TechnicalCategory(
            category="backend",
            skills=[
                SkillEvaluation(name="Python", type="Indispensable", level="Avanzado", status="Cumple"),
                SkillEvaluation(name="FastAPI", type="Indispensable", level="Intermedio", status="Cumple"),
                SkillEvaluation(name="Java", type="Indispensable", level="Básico", status="No Cumple"),
            ]
        ),
        TechnicalCategory(
            category="cloud",
            skills=[
                SkillEvaluation(name="Azure", type="Deseable", level="Intermedio", status="Cumple"),
                SkillEvaluation(name="Kubernetes", type="Deseable", level="Básico", status="No Cumple"),
            ]
        )
    ]

    summary = calculate_evaluation_summary(categories)

    # 3 indispensables (2 cumplen, 1 no cumple)
    assert summary.requiredSkillsMet == 2
    assert summary.totalRequiredSkills == 3

    # 2 deseables (1 cumple, 1 no cumple)
    assert summary.optionalSkillsMet == 1
    assert summary.totalOptionalSkills == 2

    # Total: 3 de 5 cumplidos = 60%
    assert summary.matchPercentage == 60
    assert "60%" in summary.recommendation


def test_scoring_empty():
    summary = calculate_evaluation_summary([])
    assert summary.matchPercentage == 0
    assert summary.requiredSkillsMet == 0
    assert summary.totalRequiredSkills == 0
