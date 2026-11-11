"""Раздел 4 (передача детонации r_д) и раздел 5 (действие УВВ R_увв) по Приложению 11 Приказа № 343."""

import math

from explosions_core.calc.safe_distances import FORMULA_10, calculate_detonation_distance, detonation_charge_placement
from explosions_core.domain import (
    ChargePlacementType,
    DetonationPairResult,
    StorageBuilding,
    UVVDistanceResult,
    UVVMethod,
    WarehouseProjectInput,
)
from explosions_core.export.reports.docx_styles import add_heading, add_paragraph, add_table
from explosions_core.export.reports.note.common import add_step, add_violations, fmt, storage_index
from explosions_core.norms.references import CLAUSE_UVV, CLAUSE_UVV_TABLE_3

PLACEMENT_TEXT = {
    ChargePlacementType.OPEN_SURFACE: "открытый",
    ChargePlacementType.BURIED_OWN_HEIGHT: "углубленный",
}


def _classes_text(storage: StorageBuilding) -> str:
    classes = sorted({item.detonation_class.value for item in storage.items if item.detonation_class is not None})
    return ", ".join(classes) if classes else "не задан"


def _add_direction_step(
    doc,
    active: StorageBuilding,
    passive: StorageBuilding,
    q_kg: float,
    k_d: float,
    b_passive: float,
    r_result: float,
) -> None:
    r_19 = calculate_detonation_distance(q_kg, k_d, b_passive)
    active_place = PLACEMENT_TEXT[detonation_charge_placement(active)]
    passive_place = PLACEMENT_TEXT[detonation_charge_placement(passive)]
    table_note = "" if abs(r_result - r_19) < 1e-9 else f"; по таблице 5 — {fmt(r_result)} м, принято большее"
    add_step(
        doc,
        f"Направление «{active.name}» → «{passive.name}» (активный → пассивный)",
        "r_{д} = K_{д} · ∛Q · ∜b  (формула (19))",
        f"K_{{д}} = {fmt(k_d)} (таблица 4: активный — {_classes_text(active)}, {active_place}; пассивный — "
        f"{_classes_text(passive)}, {passive_place}); Q = {fmt(q_kg)} кг; b = {fmt(b_passive)} м: "
        f"r_{{д}} = {fmt(k_d)} · {fmt(q_kg ** (1.0 / 3.0))} · {fmt(b_passive ** 0.25)} = {fmt(r_19)} м{table_note}",
        f"r_{{д}} = {fmt(r_result)} м (п. 15, 16, 19 Приложения 11)",
    )


def add_section_4(
    doc,
    project: WarehouseProjectInput,
    detonation_results: list[DetonationPairResult],
    tables: dict,
) -> None:
    add_heading(doc, "4. Расчет безопасных расстояний по передаче детонации между хранилищами ВМ (r_д)", level=1)
    add_paragraph(
        doc,
        "Q — масса ВВ активного заряда, кг; b — меньший линейный размер пассивного заряда (ширина штабеля), м; "
        "обвалованные хранилища приравниваются к зарядам, углубленным на свою высоту (п. 16 Приложения 11); "
        "для пассивного заряда из разных ВМ K_д принимается по наиболее чувствительному ВМ (п. 19).",
    )
    storages = storage_index(project)
    rows: list[list[str]] = []
    red_rows: set[int] = set()
    for pair in detonation_results:
        storage_i = storages[pair.storage_i_id]
        storage_j = storages[pair.storage_j_id]
        add_paragraph(doc, f"Пара «{storage_i.name}» ↔ «{storage_j.name}»", bold=True)
        _add_direction_step(doc, storage_i, storage_j, pair.q_i_kg, pair.k_d_i_to_j, pair.b_j_m, pair.r_d_i_to_j_m)
        _add_direction_step(doc, storage_j, storage_i, pair.q_j_kg, pair.k_d_j_to_i, pair.b_i_m, pair.r_d_j_to_i_m)
        axial_text = ""
        if pair.axial_min_distance_m is not None:
            axial_text = f"; хранилища по одной оси: 2 · B_{{max}} = {fmt(pair.axial_min_distance_m)} м (п. 17)"
        margin = pair.actual_clear_distance_m - pair.governing_required_r_d_m
        add_step(
            doc,
            "Сопоставление с фактическим расстоянием в свету",
            "r_{д,расч} = max(r_{д,i→j}; r_{д,j→i})  (п. 17);  Запас = L_{факт} − r_{д,расч}",
            f"r_{{д,расч}} = max({fmt(pair.r_d_i_to_j_m)}; {fmt(pair.r_d_j_to_i_m)}){axial_text} → "
            f"{fmt(pair.governing_required_r_d_m)} м; L_{{факт}} = {fmt(pair.actual_clear_distance_m)} м; "
            f"Запас = {fmt(margin)} м",
            f"L_{{факт}} {'≥' if pair.is_safe else '<'} r_{{д,расч}}: "
            f"{'соответствует' if pair.is_safe else 'не соответствует'} п. 15 и 17 Приложения 11 Приказа № 343",
            ok=pair.is_safe,
        )
        add_violations(doc, pair.violations)
        status = "Соответствует п. 15, 17 Прил. 11" if pair.is_safe else "Нарушение п. 15, 17 Прил. 11"
        for active, passive, q_kg, k_d, b_m, r_dir in (
            (storage_i, storage_j, pair.q_i_kg, pair.k_d_i_to_j, pair.b_j_m, pair.r_d_i_to_j_m),
            (storage_j, storage_i, pair.q_j_kg, pair.k_d_j_to_i, pair.b_i_m, pair.r_d_j_to_i_m),
        ):
            if not pair.is_safe:
                red_rows.add(len(rows))
            rows.append(
                [
                    active.name,
                    passive.name,
                    fmt(q_kg),
                    fmt(k_d),
                    fmt(b_m),
                    fmt(r_dir),
                    fmt(pair.actual_clear_distance_m),
                    fmt(margin),
                    status,
                ]
            )
    add_paragraph(doc, "Таблица 4.1 — Матрица проверки безопасных расстояний по передаче детонации", bold=True)
    add_table(
        doc,
        [
            "Активное хранилище",
            "Пассивное хранилище",
            "Q, кг",
            "K_д",
            "b, м",
            "r_д, м",
            "L_факт, м",
            "Запас, м",
            "Статус",
        ],
        rows,
        red_rows=frozenset(red_rows),
    )


def add_section_5(doc, project: WarehouseProjectInput, uvv_results: list[UVVDistanceResult]) -> None:
    add_heading(doc, "5. Расчет безопасных расстояний по действию ударной воздушной волны (R_увв)", level=1)
    add_paragraph(
        doc,
        "Q — масса ВВ, кг (свойства ВВ не учитываются). Формула (10) применяется для степеней 1–3 при Q > 10 т "
        "(открытый заряд) и для степеней 1–2 при Q > 20 т (углубленный заряд), в остальных случаях — формула (11). "
        "Обвалованные хранилища при 1–2 степени рассматриваются как наружные заряды, выше 2-й — как углубленные "
        "на свою высоту. Из диапазона таблицы 2 принимается наибольшее значение, если коэффициент не задан "
        "проектом для конкретного объекта (п. 10 Приложения 11).",
    )
    if any(result.method == UVVMethod.TABLE_3 for result in uvv_results):
        add_paragraph(
            doc,
            f"Расстояния приняты по {CLAUSE_UVV_TABLE_3} по расчетным формулам таблицы для категории "
            "объекта; масса Q — вместимость наибольшего хранилища ВМ (примечание к таблице 3).",
        )
    storages = storage_index(project)
    objects = {obj.object_id: obj for obj in project.external_targets}
    rows: list[list[str]] = []
    red_rows: set[int] = set()
    for result in uvv_results:
        storage = storages[result.storage_id]
        obj = objects[result.object_id]
        q_kg = result.explosive_mass_kg
        coeff = result.applied_coeff
        k_rel = obj.topography_reduction_coeff
        required = result.required_distance_m
        placement = PLACEMENT_TEXT[result.placement]
        range_text = (
            f"диапазон таблицы 2: {fmt(result.kv_range[0])}–{fmt(result.kv_range[1])}" if result.kv_range else ""
        )
        if obj.custom_kv_override is not None:
            range_text += "; принят коэффициент, заданный проектом"
        add_paragraph(
            doc,
            f"«{storage.name}» → «{obj.name}» (степень повреждения {obj.allowed_damage_degree}, заряд {placement})",
            bold=True,
        )
        if result.method == UVVMethod.TABLE_3:
            cbrt = result.formula_used == FORMULA_10
            root = q_kg ** (1.0 / 3.0) if cbrt else math.sqrt(q_kg)
            formula = (
                f"R_{{увв}} = k · {'∛' if cbrt else '√'}Q  (таблица 3, объекты {obj.table3_object_category})"
            )
            substitution = (
                f"k = {fmt(coeff)}; Q = {fmt(q_kg)} кг: R_{{увв}} = {fmt(coeff)} · {fmt(root)} = {fmt(required)} м"
            )
            norm_text = CLAUSE_UVV_TABLE_3
        else:
            if result.formula_used == FORMULA_10:
                formula = "r_{в} = K_{в} · ∛Q · k_{рел}  (формула (10))"
                root, symbol = q_kg ** (1.0 / 3.0), "K_{в}"
            else:
                formula = "r_{в} = k_{в} · √Q · k_{рел}  (формула (11))"
                root, symbol = math.sqrt(q_kg), "k_{в}"
            substitution = (
                f"{symbol} = {fmt(coeff)} ({range_text}); Q = {fmt(q_kg)} кг; k_{{рел}} = {fmt(k_rel)}: "
                f"r_{{в}} = {fmt(coeff)} · {fmt(root)} · {fmt(k_rel)} = {fmt(required)} м"
            )
            norm_text = CLAUSE_UVV
        conclusion = (
            f"L_{{факт}} = {fmt(result.actual_distance_m)} м {'≥' if result.is_safe else '<'} "
            f"R_{{увв}} = {fmt(required)} м: "
            f"{'соответствует' if result.is_safe else 'не соответствует'} {norm_text}"
        )
        add_step(doc, "Безопасное расстояние по УВВ", formula, substitution, conclusion, ok=result.is_safe)
        add_violations(doc, result.violations)
        if not result.is_safe:
            red_rows.add(len(rows))
        rows.append(
            [
                storage.name,
                obj.name,
                str(obj.allowed_damage_degree),
                placement,
                fmt(q_kg),
                fmt(coeff),
                fmt(required),
                fmt(result.actual_distance_m),
                fmt(result.safety_margin_m),
                "Соответствует" if result.is_safe else "Нарушение",
            ]
        )
    add_paragraph(doc, "Таблица 5.1 — Ведомость проверки безопасных расстояний по действию УВВ", bold=True)
    add_table(
        doc,
        ["Хранилище", "Объект", "Степень", "Заряд", "Q, кг", "K_в/k_в", "R_увв, м", "L_факт, м", "Запас, м", "Статус"],
        rows,
        red_rows=frozenset(red_rows),
    )
