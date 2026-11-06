"""Общие хелперы расчетно-пояснительной записки: форматирование, шаги «Формула -> Подстановка -> Вывод»."""

from explosions_core.calc.geometry import storage_key
from explosions_core.domain import NormativeViolation, StorageBuilding, WarehouseProjectInput
from explosions_core.export.reports.docx_styles import add_formula, add_paragraph, add_red_bold_paragraph


def fmt(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def storage_index(project: WarehouseProjectInput) -> dict[str, StorageBuilding]:
    return {storage_key(storage): storage for storage in project.storages}


def cmp_sign(actual: float, required: float, *, at_most: bool) -> str:
    if at_most:
        return "≤" if actual <= required + 1e-9 else ">"
    return "≥" if actual >= required - 1e-9 else "<"


def add_step(
    doc,
    title: str,
    formula: str,
    substitution: str,
    conclusion: str,
    ok: bool = True,
) -> None:
    add_paragraph(doc, title, bold=True)
    add_formula(doc, formula)
    add_paragraph(doc, f"Подстановка: {substitution}")
    if ok:
        add_paragraph(doc, f"Вывод: {conclusion}")
    else:
        add_red_bold_paragraph(doc, f"Вывод: {conclusion}")


def add_violations(doc, violations: list[NormativeViolation]) -> None:
    for violation in violations:
        add_red_bold_paragraph(
            doc,
            f"Нарушение {violation.code}: {violation.description}. "
            f"Факт: {violation.actual_value}, норма: {violation.required_value}. Ссылка: {violation.clause}.",
        )
