"""Подготовка результата расчета к показу: строки таблиц и итоговый статус (без Qt).

Все числа берутся из `ProjectCalculationResult`; здесь только форматирование и подписи.
"""

from explosions_core.domain import CalculationIssue, NormativeViolation, ProjectCalculationResult
from explosions_core.gui.labels import MODULE_LABELS, SEVERITY_LABELS, enum_label

STATUS_OK = "ok"
STATUS_FAIL = "fail"
STATUS_WARN = "warn"


def fmt(value: float | int | None, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}".replace(".", ",")


def overall_status(result: ProjectCalculationResult) -> tuple[str, str]:
    """(код статуса, текст баннера) для верхней строки окна результатов."""
    if result.errors:
        return STATUS_FAIL, f"Расчет выполнен с ошибками: {len(result.errors)}. Результаты неполные."
    if not result.is_compliant:
        return STATUS_FAIL, f"Проект НЕ соответствует нормам: нарушений {len(result.all_violations)}."
    if result.issues:
        return STATUS_WARN, "Нарушений нет, но есть замечания к исходным данным (см. вкладку «Замечания»)."
    return STATUS_OK, "Проект соответствует нормам: нарушений не найдено."


def violation_rows(violations: list[NormativeViolation]) -> list[list[str]]:
    return [
        [v.code, v.description, fmt(v.actual_value), fmt(v.required_value), v.clause]
        for v in violations
    ]


def issue_rows(issues: list[CalculationIssue]) -> list[list[str]]:
    return [
        [
            SEVERITY_LABELS.get(issue.severity, issue.severity),
            MODULE_LABELS.get(issue.module, issue.module),
            issue.object_id or "—",
            issue.message,
        ]
        for issue in issues
    ]


def detonation_rows(result: ProjectCalculationResult) -> list[list[str]]:
    rows: list[list[str]] = []
    for pair in result.detonation_results:
        rows.append(
            [
                f"{pair.storage_i_id} ↔ {pair.storage_j_id}",
                fmt(pair.q_i_kg),
                fmt(pair.q_j_kg),
                fmt(pair.governing_required_r_d_m),
                fmt(pair.actual_clear_distance_m),
                fmt(pair.actual_clear_distance_m - pair.governing_required_r_d_m),
                "соответствует" if pair.is_safe else "НАРУШЕНИЕ",
            ]
        )
    return rows


def uvv_rows(result: ProjectCalculationResult) -> list[list[str]]:
    rows: list[list[str]] = []
    for item in result.uvv_results:
        rows.append(
            [
                item.storage_id,
                item.object_id,
                fmt(item.explosive_mass_kg),
                fmt(item.required_distance_m),
                fmt(item.actual_distance_m),
                fmt(item.safety_margin_m),
                "соответствует" if item.is_safe else "НАРУШЕНИЕ",
            ]
        )
    return rows


def sizing_rows(result: ProjectCalculationResult) -> list[list[str]]:
    rows: list[list[str]] = []
    for record in result.sizing_records:
        s = record.result
        rows.append(
            [
                record.storage_id,
                str(s.total_units_required),
                str(s.tiers_per_shelf),
                fmt(s.total_loaded_height_m),
                fmt(s.min_internal_width_m),
                fmt(s.min_internal_length_m),
                fmt(s.min_internal_height_m),
                "НАРУШЕНИЕ" if s.violations else "соответствует",
            ]
        )
    return rows


def berm_rows(result: ProjectCalculationResult) -> list[list[str]]:
    rows: list[list[str]] = []
    for record in result.berm_records:
        b = record.result
        rows.append(
            [
                record.storage_id,
                fmt(b.berm_height_m),
                fmt(b.crest_width_m),
                fmt(b.base_width_m),
                fmt(b.total_earthwork_volume_m3, 1),
                "НАРУШЕНИЕ" if b.violations else "соответствует",
            ]
        )
    return rows


def lightning_rows(result: ProjectCalculationResult) -> list[list[str]]:
    rows: list[list[str]] = []
    for record in result.lightning_records:
        lr = record.result
        rows.append(
            [
                record.storage_id,
                enum_label(record.method),
                fmt(lr.min_recommended_mast_height_m),
                "да" if lr.is_fully_protected else "нет",
                "НАРУШЕНИЕ" if lr.violations else "соответствует",
            ]
        )
    return rows
