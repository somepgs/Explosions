"""Тексты промежуточных результатов на шагах мастера 2–5 (без Qt).

Значения берутся из расчета ядра (`calculate_project`) или из валидаторов; здесь ничего не пересчитывается.
Каждая функция возвращает строки для панели «Результат» справа на шаге.
"""

from typing import Any

from pydantic import ValidationError

from explosions_core.domain import NormativeViolation, ProjectCalculationResult, StorageBuilding
from explosions_core.gui.explanations import explain_violation
from explosions_core.gui.labels import enum_label
from explosions_core.gui.results_view import fmt
from explosions_core.norms.references import DRAWING_CLAUSE_DETONATION
from explosions_core.validators.compatibility import check_classification_codes, check_storage_compatibility
from explosions_core.validators.layout_and_perimeter import validate_internal_layout

NO_RESULT_TEXT = "Расчет пока невозможен: заполните обязательные поля этого шага и шага «Хранилища и ВМ»."


def _violation_lines(violations: list[NormativeViolation]) -> list[str]:
    lines = []
    for violation in violations:
        action = explain_violation(violation).action
        lines.append(f"✖ {violation.description} [{violation.clause}]")
        if action:
            lines.append(f"    Что сделать: {action}")
    return lines


def _issue_lines(result: ProjectCalculationResult, key: str, module: str) -> list[str]:
    return [
        f"✖ {issue.message}"
        for issue in result.issues
        if issue.module == module and issue.object_id == key and issue.severity == "error"
    ]


def storage_check_lines(storage: dict[str, Any]) -> list[str]:
    """Проверка совместимости (п. 8–9) и шифров ТР ТС для хранилища шага 2."""
    if not storage.get("items"):
        return ["⚠ Добавьте хотя бы одну партию ВМ: без нее хранилище не рассчитывается."]
    try:
        building = StorageBuilding.model_validate(storage)
    except ValidationError:
        return ["⚠ Заполните обязательные поля хранилища и партий ВМ (наименование, масса, группа)."]
    violations = check_storage_compatibility(building).violations + check_classification_codes(building).violations
    total = sum(item.mass_kg for item in building.items)
    lines = [f"Партий ВМ: {len(building.items)}, общая масса нетто {fmt(total)} кг."]
    missing_class = [item.name for item in building.items if item.detonation_class is None and not item.is_initiating_device]
    if missing_class:
        lines.append("⚠ Не задан класс по таблице 4 Приложения 11: " + ", ".join(missing_class))
    if violations:
        lines.extend(_violation_lines(violations))
    else:
        lines.append("✔ Совместимость групп (п. 8–9 Приказа № 343) и шифры ТР ТС в порядке.")
    return lines


def layout_check_lines(storage: dict[str, Any]) -> list[str]:
    """Проверка фактической планировки хранилища (п. 579–580), если она задана на шаге 3."""
    if storage.get("layout") is None:
        return []
    try:
        building = StorageBuilding.model_validate(storage)
    except ValidationError:
        return ["⚠ Фактическая планировка: заполните способ хранения и упаковку."]
    violations = validate_internal_layout(building).violations
    lines = ["Фактическая планировка:"]
    if violations:
        lines.extend(_violation_lines(violations))
    else:
        lines.append("✔ Заданные отступы, проходы и высоты соответствуют п. 579–580.")
    return lines


def sizing_preview_lines(result: ProjectCalculationResult | None, key: str, design: dict[str, Any] | None) -> list[str]:
    if design is None or design.get("sizing") is None:
        return ["Раздел «Планировка и габариты» не включен. Включите его, чтобы рассчитать стеллажи или штабели."]
    if result is None:
        return [NO_RESULT_TEXT]
    record = next((r for r in result.sizing_records if r.storage_id == key), None)
    if record is None:
        return _issue_lines(result, key, "sizing") or [NO_RESULT_TEXT]
    data = record.result
    lines = [
        f"Мест тары: {data.total_units_required} шт., масса брутто {fmt(data.total_gross_weight_kg)} кг.",
        f"Полок или ярусов по высоте: {data.shelves_or_tiers_count}, ярусов на полке: {data.tiers_per_shelf}.",
        f"Высота груза от пола: {fmt(data.total_loaded_height_m)} м.",
        f"Ширина прохода: {fmt(data.required_aisle_width_m)} м, длина линии: {fmt(data.line_length_m)} м.",
        (
            f"Минимальные внутренние размеры: {fmt(data.min_internal_length_m)} × {fmt(data.min_internal_width_m)} м, "
            f"высота {fmt(data.min_internal_height_m)} м."
        ),
        f"Площадь: {fmt(data.total_internal_area_m2)} м², использование {fmt(data.area_utilization_coeff)}.",
    ]
    if data.violations:
        lines.extend(_violation_lines(data.violations))
    else:
        lines.append("✔ Нарушений п. 579–580 Приказа № 343 нет.")
    return lines


def placement_preview_lines(result: ProjectCalculationResult | None, key: str, design: dict[str, Any] | None) -> list[str]:
    lines: list[str] = []
    if result is not None:
        pairs = [p for p in result.detonation_results if key in (p.storage_i_id, p.storage_j_id)]
        for pair in pairs:
            other = pair.storage_j_id if pair.storage_i_id == key else pair.storage_i_id
            mark = "✔" if pair.is_safe else "✖"
            lines.append(
                f"{mark} До {other}: L_факт = {fmt(pair.actual_clear_distance_m)} м, "
                f"требуется r_д = {fmt(pair.governing_required_r_d_m)} м ({DRAWING_CLAUSE_DETONATION})."
            )
        if not pairs:
            lines.append("Расстояния r_д: нет второго хранилища с координатами.")
    if design is None or design.get("berm") is None:
        lines.append("Обвалование не задано.")
        return lines
    if result is None:
        lines.append(NO_RESULT_TEXT)
        return lines
    record = next((r for r in result.berm_records if r.storage_id == key), None)
    if record is None:
        lines.extend(_issue_lines(result, key, "berm") or [NO_RESULT_TEXT])
        return lines
    berm = record.result
    lines.extend(
        [
            f"Высота вала: {fmt(berm.berm_height_m)} м, ширина по гребню {fmt(berm.crest_width_m)} м, по подошве {fmt(berm.base_width_m)} м.",
            f"Объем грунта: {fmt(berm.total_earthwork_volume_m3)} м³.",
            f"Габарит обвалования: {fmt(berm.outer_footprint_length_m)} × {fmt(berm.outer_footprint_width_m)} м.",
        ]
    )
    if berm.violations:
        lines.extend(_violation_lines(berm.violations))
    else:
        lines.append("✔ Нарушений п. 603–605 Приказа № 343 нет.")
    return lines


def lightning_preview_lines(result: ProjectCalculationResult | None, key: str, design: dict[str, Any] | None) -> list[str]:
    if design is None or design.get("lightning") is None:
        return ["Молниезащита не задана. Для постоянного и временного хранилища она обязательна (п. 691)."]
    if result is None:
        return [NO_RESULT_TEXT]
    record = next((r for r in result.lightning_records if r.storage_id == key), None)
    if record is None:
        return _issue_lines(result, key, "lightning") or [
            "Расчет невозможен: задайте высоту карниза и конька и хотя бы одну мачту."
        ]
    data = record.result
    lines = [f"Метод: {enum_label(record.method)}."]
    if data.min_recommended_mast_height_m is not None:
        lines.append(f"Рекомендуемая высота мачт: не менее {fmt(data.min_recommended_mast_height_m, 1)} м.")
    if data.is_fully_protected:
        lines.append("✔ Все контрольные точки кровли входят в зону защиты.")
    else:
        lines.append("✖ Вне зоны защиты: " + ", ".join(data.unprotected_points))
    if data.violations:
        lines.extend(_violation_lines(data.violations))
    return lines
