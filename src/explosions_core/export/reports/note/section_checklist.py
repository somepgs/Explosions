"""Раздел 8: сводный протокол нормативного контроля (чек-лист соответствия Приказу № 343)."""

from explosions_core.calc.geometry import storage_key
from explosions_core.calc.lightning_protection import lightning_required_violation
from explosions_core.domain import (
    DetonationPairResult,
    NormativeViolation,
    UVVDistanceResult,
    WarehouseDuration,
    WarehouseProjectInput,
)
from explosions_core.export.reports.docx_styles import add_heading, add_paragraph, add_red_bold_paragraph, add_table
from explosions_core.export.reports.note.records import BermRecord, LightningRecord, StorageSizingRecord
from explosions_core.norms.references import (
    CLAUSE_BERM,
    CLAUSE_COMPATIBILITY,
    CLAUSE_COMPATIBILITY_EXCEPTION,
    CLAUSE_DETONATION,
    CLAUSE_LAYOUT,
    CLAUSE_LIGHTNING_REQUIRED,
    CLAUSE_LIGHTNING_SO153,
    CLAUSE_LIGHTNING_SPHERE,
    CLAUSE_MOBILE_PAYLOAD,
    CLAUSE_MOBILE_POWDER,
    CLAUSE_PERIMETER_PERMANENT,
    CLAUSE_PERIMETER_SHORT_TERM,
    CLAUSE_PERIMETER_TEMPORARY,
    CLAUSE_PRP,
    CLAUSE_RACK,
    CLAUSE_STACK,
    CLAUSE_UVV,
)
from explosions_core.validators.compatibility import validate_compatibility
from explosions_core.validators.layout_and_perimeter import (
    governing_warehouse_duration,
    validate_internal_layout,
    validate_mobile_warehouse,
    validate_perimeter,
    validate_prp,
)

PERIMETER_CLAUSES = {
    WarehouseDuration.PERMANENT: CLAUSE_PERIMETER_PERMANENT,
    WarehouseDuration.TEMPORARY: CLAUSE_PERIMETER_TEMPORARY,
    WarehouseDuration.SHORT_TERM: CLAUSE_PERIMETER_SHORT_TERM,
}

CHECK_ROW_COLUMNS = ["Проверка", "Норма", "Статус", "Детали"]


def _check_row(
    check: str,
    clause: str,
    violations: list[NormativeViolation],
    applicable: bool = True,
) -> tuple[list[str], bool]:
    if not applicable:
        return [check, clause, "Не применяется", "—"], False
    if not violations:
        return [check, clause, "Соответствует", "—"], False
    details = "; ".join(
        f"{v.code}: {v.description} (факт {v.actual_value}, норма {v.required_value})" for v in violations
    )
    return [check, clause, "Нарушение", details], True


def add_section_8(
    doc,
    project: WarehouseProjectInput,
    sizing_records: list[StorageSizingRecord],
    detonation_results: list[DetonationPairResult],
    uvv_results: list[UVVDistanceResult],
    berm_records: list[BermRecord],
    lightning_records: list[LightningRecord],
) -> None:
    add_heading(doc, "8. Сводный протокол нормативного контроля (чек-лист соответствия Приказу № 343)", level=1)
    duration = governing_warehouse_duration(project)
    protected = {record.storage_id for record in lightning_records}
    lightning_violations = [v for r in lightning_records for v in r.result.violations]
    for storage in project.storages:
        key = storage_key(storage)
        missing = lightning_required_violation(storage, key, has_protection=key in protected)
        if missing is not None:
            lightning_violations.append(missing)
    checks: list[tuple[str, str, list[NormativeViolation], bool]] = [
        (
            "Совместимость ВМ в хранилищах",
            f"{CLAUSE_COMPATIBILITY}; исключения — {CLAUSE_COMPATIBILITY_EXCEPTION}",
            list(validate_compatibility(project.storages).violations),
            True,
        ),
        (
            "Внутренняя планировка хранилищ",
            CLAUSE_LAYOUT,
            [v for s in project.storages for v in validate_internal_layout(s).violations],
            True,
        ),
        (
            "Расчет стеллажей, штабелей и габаритов",
            f"{CLAUSE_STACK}; {CLAUSE_RACK}",
            [v for r in sizing_records for v in r.result.violations],
            bool(sizing_records),
        ),
        (
            "Генплан: ограда, запретная зона, расстояния от ограды, запрет огня 100 м",
            PERIMETER_CLAUSES[duration],
            list(validate_perimeter(project).violations),
            True,
        ),
        (
            "Погрузочно-разгрузочная площадка (ПРП)",
            CLAUSE_PRP,
            list(validate_prp(project).violations),
            project.unloading_platform is not None,
        ),
        (
            "Перевозка ВМ: загрузка до 2/3 грузоподъемности, пороха не ближе 0,5 м",
            f"{CLAUSE_MOBILE_PAYLOAD}; {CLAUSE_MOBILE_POWDER}",
            list(validate_mobile_warehouse(project).violations),
            project.mobile_warehouse is not None,
        ),
        (
            "Обвалование хранилищ",
            CLAUSE_BERM,
            [v for r in berm_records for v in r.result.violations],
            bool(berm_records),
        ),
        (
            "Молниезащита хранилищ",
            f"{CLAUSE_LIGHTNING_REQUIRED}; {CLAUSE_LIGHTNING_SPHERE} / {CLAUSE_LIGHTNING_SO153}",
            lightning_violations,
            bool(lightning_records) or bool(lightning_violations),
        ),
        (
            "Безопасные расстояния по действию УВВ",
            CLAUSE_UVV,
            [v for r in uvv_results for v in r.violations],
            bool(uvv_results),
        ),
        (
            "Безопасные расстояния по передаче детонации",
            CLAUSE_DETONATION,
            [v for r in detonation_results for v in r.violations],
            bool(detonation_results),
        ),
    ]
    rows: list[list[str]] = []
    red_rows: set[int] = set()
    total_violations = 0
    for check, clause, violations, applicable in checks:
        row, is_red = _check_row(check, clause, violations, applicable)
        if is_red:
            red_rows.add(len(rows))
            total_violations += len(violations)
        rows.append(row)
    add_table(doc, CHECK_ROW_COLUMNS, rows, red_rows=frozenset(red_rows))
    if total_violations:
        add_red_bold_paragraph(doc, f"Выявлено нарушений Приказа № 343: {total_violations}. Требуется корректировка проекта.")
    else:
        add_paragraph(doc, "Нарушения Приказа № 343 по проверенным пунктам не выявлены.", bold=True)
