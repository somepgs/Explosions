"""Раздел 4 (передача детонации r_д) и раздел 5 (действие УВВ R_увв)."""

import math

from explosions_core.norms.constants_rk343 import DEFAULT_STACK_WIDTH_B_M, UVV_FORMULA_MASS_THRESHOLD_KG
from explosions_core.calc.safe_distances import select_detonation_profile
from explosions_core.domain import (
    DetonationPairResult,
    StorageBuilding,
    UVVDistanceResult,
    WarehouseProjectInput,
)
from explosions_core.export.reports.docx_styles import add_heading, add_paragraph, add_table
from explosions_core.export.reports.note.common import add_step, add_violations, fmt, storage_index


def _stack_width(storage: StorageBuilding) -> float:
    return storage.stack_width_b_m if storage.stack_width_b_m is not None else DEFAULT_STACK_WIDTH_B_M


def _profile_coefficient(active: StorageBuilding, passive: StorageBuilding, tables: dict) -> tuple[str | None, float | None]:
    try:
        profile = select_detonation_profile(active, passive)
    except NotImplementedError:
        return None, None
    return profile, tables["detonation_coefficients_kd"]["profiles"][profile]


def _add_direction_step(
    doc,
    active: StorageBuilding,
    passive: StorageBuilding,
    q_tnt: float,
    r_result: float,
    tables: dict,
) -> float | None:
    profile, k_d = _profile_coefficient(active, passive, tables)
    title = f"Направление «{active.name}» → «{passive.name}» (активный → пассивный)"
    formula = "r_{д} = K_{д} · ∛Q (ф. 18);  r_{д} = K_{д} · √(Q · b) / b (ф. 19);  r_{д} = max(ф. 18; ф. 19)"
    if k_d is None:
        add_step(
            doc,
            title,
            formula,
            "K_{д} не определен для данной пары",
            "расчет невозможен, требуется таблица Приложения 11 Приказа № 343",
            ok=False,
        )
        return None
    b_m = _stack_width(active)
    r_18 = k_d * (q_tnt ** (1.0 / 3.0))
    r_19 = k_d * math.sqrt(q_tnt * b_m) / b_m
    add_step(
        doc,
        title,
        formula,
        f"K_{{д}} = {fmt(k_d)} ({profile}); Q = {fmt(q_tnt)} кг; b = {fmt(b_m)} м; "
        f"r_{{д,18}} = {fmt(k_d)} · ∛{fmt(q_tnt)} = {fmt(r_18)} м; "
        f"r_{{д,19}} = {fmt(k_d)} · √({fmt(q_tnt)} · {fmt(b_m)}) / {fmt(b_m)} = {fmt(r_19)} м",
        f"принято r_{{д}} = {fmt(r_result)} м (п. 15 Приложения 11, п. 112 Приказа № 343)",
    )
    return k_d


def add_section_4(
    doc,
    project: WarehouseProjectInput,
    detonation_results: list[DetonationPairResult],
    tables: dict,
) -> None:
    add_heading(doc, "4. Расчет безопасных расстояний по передаче детонации между хранилищами ВМ (r_д)", level=1)
    storages = storage_index(project)
    rows: list[list[str]] = []
    red_rows: set[int] = set()
    for pair in detonation_results:
        active_i = storages[pair.storage_i_id]
        passive_j = storages[pair.storage_j_id]
        add_paragraph(doc, f"Пара «{active_i.name}» ↔ «{passive_j.name}»", bold=True)
        k_ij = _add_direction_step(doc, active_i, passive_j, pair.q_i_tnt_kg, pair.r_d_i_to_j_m, tables)
        k_ji = _add_direction_step(doc, passive_j, active_i, pair.q_j_tnt_kg, pair.r_d_j_to_i_m, tables)
        margin = pair.actual_clear_distance_m - pair.governing_required_r_d_m
        add_step(
            doc,
            "Сопоставление с фактическим расстоянием в свету",
            "r_{д,расч} = max(r_{д,i→j}; r_{д,j→i});  Запас = L_{факт} − r_{д,расч}",
            f"r_{{д,расч}} = max({fmt(pair.r_d_i_to_j_m)}; {fmt(pair.r_d_j_to_i_m)}) = "
            f"{fmt(pair.governing_required_r_d_m)} м; L_{{факт}} = {fmt(pair.actual_clear_distance_m)} м; "
            f"Запас = {fmt(margin)} м",
            f"L_{{факт}} {'≥' if pair.is_safe else '<'} r_{{д,расч}}: "
            f"{'соответствует' if pair.is_safe else 'не соответствует'} п. 15 Приложения 11 Приказа № 343",
            ok=pair.is_safe,
        )
        add_violations(doc, pair.violations)
        status = "Соответствует п. 15 Прил. 11" if pair.is_safe else "Нарушение п. 15 Прил. 11"
        for active, passive, q_tnt, k_d, r_dir in (
            (active_i, passive_j, pair.q_i_tnt_kg, k_ij, pair.r_d_i_to_j_m),
            (passive_j, active_i, pair.q_j_tnt_kg, k_ji, pair.r_d_j_to_i_m),
        ):
            if not pair.is_safe:
                red_rows.add(len(rows))
            rows.append(
                [
                    active.name,
                    passive.name,
                    fmt(q_tnt),
                    fmt(k_d) if k_d is not None else "—",
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
            "Q_тэ, кг",
            "K_д",
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
    storages = storage_index(project)
    objects = {obj.object_id: obj for obj in project.external_targets}
    rows: list[list[str]] = []
    red_rows: set[int] = set()
    for result in uvv_results:
        storage = storages[result.storage_id]
        obj = objects[result.object_id]
        q_tnt = result.equivalent_tnt_mass_kg
        coeff = result.applied_coeff_kv
        k_rel = obj.topography_reduction_coeff
        required = result.required_distance_m
        add_paragraph(
            doc,
            f"«{storage.name}» → «{obj.name}» (допустимая степень повреждения {obj.allowed_damage_degree})",
            bold=True,
        )
        if q_tnt > UVV_FORMULA_MASS_THRESHOLD_KG:
            formula = "r_{в} = K_{в} · ∛Q_{тэ} · k_{рел}  (Q_{тэ} > 1000 кг)"
            substitution = (
                f"K_{{в}} = {fmt(coeff)}; ∛{fmt(q_tnt)} = {fmt(q_tnt ** (1.0 / 3.0))}; k_{{рел}} = {fmt(k_rel)}: "
                f"r_{{в}} = {fmt(coeff)} · {fmt(q_tnt ** (1.0 / 3.0))} · {fmt(k_rel)} = {fmt(required)} м"
            )
        else:
            formula = "r_{в} = k_{в} · √Q_{тэ} · k_{рел}  (Q_{тэ} ≤ 1000 кг)"
            substitution = (
                f"k_{{в}} = {fmt(coeff)}; √{fmt(q_tnt)} = {fmt(math.sqrt(q_tnt))}; k_{{рел}} = {fmt(k_rel)}: "
                f"r_{{в}} = {fmt(coeff)} · {fmt(math.sqrt(q_tnt))} · {fmt(k_rel)} = {fmt(required)} м"
            )
        conclusion = (
            f"L_{{факт}} = {fmt(result.actual_distance_m)} м {'≥' if result.is_safe else '<'} "
            f"R_{{увв}} = {fmt(required)} м: "
            f"{'соответствует' if result.is_safe else 'не соответствует'} п. 573 и Главе 3 (п. 10) Приложения 11"
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
                fmt(q_tnt),
                fmt(required),
                fmt(result.actual_distance_m),
                fmt(result.safety_margin_m),
                "Соответствует" if result.is_safe else "Нарушение",
            ]
        )
    add_paragraph(doc, "Таблица 5.1 — Ведомость проверки безопасных расстояний по действию УВВ", bold=True)
    add_table(
        doc,
        ["Хранилище", "Объект", "Степень", "Q_тэ, кг", "R_увв, м", "L_факт, м", "Запас, м", "Статус"],
        rows,
        red_rows=frozenset(red_rows),
    )
