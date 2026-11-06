"""Раздел 8: сводный протокол нормативного контроля (чек-лист соответствия Приказу № 343)."""

from explosions_core.domain import (
    DetonationPairResult,
    NormativeViolation,
    UVVDistanceResult,
    WarehouseDuration,
    WarehouseProjectInput,
)
from explosions_core.export.reports.docx_styles import add_heading, add_paragraph, add_red_bold_paragraph, add_table
from explosions_core.export.reports.note.records import BermRecord, LightningRecord, StorageSizingRecord
from explosions_core.norms.references import CLAUSE_BERM, CLAUSE_DETONATION, CLAUSE_RACK, CLAUSE_STACK, CLAUSE_UVV
from explosions_core.validators.layout_and_perimeter import (
    validate_internal_layout,
    validate_mobile_warehouse,
    validate_perimeter,
    validate_prp,
    validate_short_term_limits,
)
from explosions_core.validators.compatibility import validate_compatibility

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
    checks: list[tuple[str, str, list[NormativeViolation], bool]] = [
        (
            "Совместимость ВМ в хранилищах",
            "п. 8 Приложения 2 Приказа № 343",
            list(validate_compatibility(project.storages).violations),
            True,
        ),
        (
            "Внутренняя планировка хранилищ",
            "п. 579–580 Приказа № 343",
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
            "Периметр, ограда, запретная зона 50 м, зона запрета огня 100 м",
            "Приказ № 343, генплан; п. 16 (зона огня)",
            list(validate_perimeter(project).violations),
            True,
        ),
        (
            "Погрузочно-разгрузочная площадка (ПРП)",
            "п. 48 Приказа № 343",
            list(validate_prp(project).violations),
            project.unloading_platform is not None,
        ),
        (
            "Кратковременные расходные склады",
            "п. 62, 64, 66, 74 Приказа № 343",
            list(validate_short_term_limits(project).violations),
            any(s.duration == WarehouseDuration.SHORT_TERM for s in project.storages),
        ),
        (
            "Передвижной склад: загрузка до 2/3 грузоподъемности",
            "п. 74 Приказа № 343",
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
            "п. 8.1.1 СП РК 2.04-103-2013",
            [v for r in lightning_records for v in r.result.violations],
            bool(lightning_records),
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
