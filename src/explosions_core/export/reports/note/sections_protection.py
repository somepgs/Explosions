"""Раздел 6 (защитное обвалование) и раздел 7 (молниезащита)."""

import math

from explosions_core.norms.constants_rk343 import (
    MAX_WALL_TO_BERM_TOE_DIST_M,
    MIN_BERM_CREST_WIDTH_M,
    MIN_WALL_TO_BERM_TOE_DIST_M,
    ZONE_A_H0_COEFF,
    ZONE_A_R0_BASE,
    ZONE_A_R0_SLOPE,
    ZONE_B_H0_COEFF,
)
from explosions_core.calc.berm_calculator import FORBIDDEN_BERM_SOIL
from explosions_core.calc.lightning_protection import (
    distance_to_building,
    generate_storage_checkpoints_3d,
    single_rod_zone,
)
from explosions_core.domain import (
    CheckPoint3D,
    LightningArresterMast,
    LightningZoneType,
    WarehouseProjectInput,
)
from explosions_core.export.reports.docx_styles import add_heading, add_paragraph, add_table
from explosions_core.export.reports.note.common import add_step, add_violations, fmt, storage_index
from explosions_core.export.reports.note.records import BermRecord, LightningRecord
from explosions_core.export.reports.note.sections_general import SOIL_LABELS
from explosions_core.norms.references import CLAUSE_BERM_SOIL

ZONE_LABELS = {LightningZoneType.ZONE_A: "Зона А", LightningZoneType.ZONE_B: "Зона Б"}


def add_section_6(doc, project: WarehouseProjectInput, berm_records: list[BermRecord]) -> None:
    add_heading(doc, "6. Расчет параметров защитных земляных валов (обвалования)", level=1)
    storages = storage_index(project)
    rows: list[list[str]] = []
    for record in berm_records:
        inp = record.berm_input
        res = record.result
        name = storages[record.storage_id].name
        add_paragraph(doc, f"Хранилище «{name}»", bold=True)
        soil_ok = inp.soil_material not in FORBIDDEN_BERM_SOIL
        add_step(
            doc,
            "Обоснование типа грунта",
            "Допустимо: пластичный (глина, суглинок) или сыпучий (песок, супесь) грунт; камень, щебень и горючие материалы запрещены",
            f"принятый грунт: {SOIL_LABELS[inp.soil_material]}",
            f"{'грунт допустим' if soil_ok else 'грунт запрещен'} по {CLAUSE_BERM_SOIL}",
            ok=soil_ok,
        )
        crest_ok = inp.crest_width_m >= MIN_BERM_CREST_WIDTH_M
        add_step(
            doc,
            "Ширина вала по гребню",
            "b_{гр} ≥ 1.50 м (п. 602–607 Приказа № 343)",
            f"{fmt(inp.crest_width_m)} ≥ {fmt(MIN_BERM_CREST_WIDTH_M)}",
            f"b_{{гр}} = {fmt(inp.crest_width_m)} м",
            ok=crest_ok,
        )
        toe_ok = MIN_WALL_TO_BERM_TOE_DIST_M <= inp.wall_to_inner_toe_clearance_m <= MAX_WALL_TO_BERM_TOE_DIST_M
        add_step(
            doc,
            "Отступ внутренней подошвы вала от стены",
            "1.00 м ≤ c ≤ 3.00 м (водоотводная канава, п. 602–607 Приказа № 343)",
            f"{fmt(MIN_WALL_TO_BERM_TOE_DIST_M)} ≤ {fmt(inp.wall_to_inner_toe_clearance_m)} ≤ "
            f"{fmt(MAX_WALL_TO_BERM_TOE_DIST_M)}",
            f"c = {fmt(inp.wall_to_inner_toe_clearance_m)} м",
            ok=toe_ok,
        )
        add_step(
            doc,
            "Высота вала",
            "H_{в} = H_{карн} + Δ_{гр}",
            f"H_{{в}} = {fmt(inp.eaves_height_m)} + {fmt(inp.crest_elevation_above_eaves_m)} = {fmt(res.berm_height_m)} м",
            f"высота вала H_{{в}} = {fmt(res.berm_height_m)} м",
        )
        tan_alpha = math.tan(math.radians(inp.natural_slope_angle_deg))
        add_step(
            doc,
            "Ширина вала по подошве",
            "B_{под} = b_{гр} + 2 · H_{в} / tg(α)",
            f"B_{{под}} = {fmt(inp.crest_width_m)} + 2 · {fmt(res.berm_height_m)} / tg({fmt(inp.natural_slope_angle_deg, 0)}°) = "
            f"{fmt(inp.crest_width_m)} + {fmt(2 * res.berm_height_m)} / {fmt(tan_alpha, 3)} = {fmt(res.base_width_m)} м",
            f"B_{{под}} = {fmt(res.base_width_m)} м",
        )
        add_step(
            doc,
            "Площадь поперечного сечения вала",
            "S_{сеч} = 0.5 · (b_{гр} + B_{под}) · H_{в}",
            f"S_{{сеч}} = 0.5 · ({fmt(inp.crest_width_m)} + {fmt(res.base_width_m)}) · {fmt(res.berm_height_m)} = "
            f"{fmt(res.cross_section_area_m2)} м²",
            f"S_{{сеч}} = {fmt(res.cross_section_area_m2)} м²",
        )
        offset = inp.wall_to_inner_toe_clearance_m + res.base_width_m / 2.0
        add_step(
            doc,
            "Длина осевой линии основного вала с проездом",
            "L_{осев} = 2 · (L + W) + 8 · (c + B_{под} / 2) − b_{пр}",
            f"L_{{осев}} = 2 · ({fmt(inp.storage_length_m)} + {fmt(inp.storage_width_m)}) + 8 · "
            f"({fmt(inp.wall_to_inner_toe_clearance_m)} + {fmt(res.base_width_m)} / 2) − "
            f"{fmt(inp.entrance_opening_width_m)} = {fmt(res.main_berm_centerline_length_m)} м",
            f"L_{{осев}} = {fmt(res.main_berm_centerline_length_m)} м (смещение осевой линии {fmt(offset)} м)",
        )
        screen_text = (
            f"L_{{экр}} = {fmt(inp.entrance_opening_width_m)} + 2 · {fmt(inp.screen_overlap_each_side_m)} = "
            f"{fmt(res.screen_berm_length_m)} м"
            if inp.has_entrance_screen_berm
            else "вал-экран не устраивается, L_{экр} = 0"
        )
        add_step(
            doc,
            "Длина защитного вала-экрана",
            "L_{экр} = b_{пр} + 2 · a_{перекр}",
            screen_text,
            f"L_{{экр}} = {fmt(res.screen_berm_length_m)} м",
        )
        add_step(
            doc,
            "Общий объем земляных работ",
            "V_{общ} = S_{сеч} · (L_{осев} + L_{экр})",
            f"V_{{общ}} = {fmt(res.cross_section_area_m2)} · ({fmt(res.main_berm_centerline_length_m)} + "
            f"{fmt(res.screen_berm_length_m)}) = {fmt(res.total_earthwork_volume_m3)} м³",
            f"V_{{общ}} = {fmt(res.total_earthwork_volume_m3)} м³",
        )
        add_violations(doc, res.violations)
        rows.append(
            [
                name,
                fmt(res.berm_height_m),
                fmt(res.crest_width_m),
                fmt(res.base_width_m),
                fmt(res.cross_section_area_m2),
                fmt(res.main_berm_centerline_length_m),
                fmt(res.screen_berm_length_m),
                fmt(res.total_earthwork_volume_m3),
            ]
        )
    add_paragraph(doc, "Таблица 6.1 — Параметры защитных земляных валов и ведомость объемов земляных работ", bold=True)
    add_table(
        doc,
        ["Хранилище", "H_в, м", "b_гр, м", "B_под, м", "S_сеч, м²", "L_осев, м", "L_экр, м", "V_общ, м³"],
        rows,
    )


def _best_mast(
    point: CheckPoint3D,
    masts: list[LightningArresterMast],
    zone: LightningZoneType,
) -> tuple[LightningArresterMast, float, float]:
    best: tuple[LightningArresterMast, float, float] | None = None
    best_margin = -math.inf
    for mast in masts:
        _, _, rx = single_rod_zone(mast.height_h_m, point.z_height_m, zone)
        distance = math.hypot(point.x_m - mast.x_m, point.y_m - mast.y_m)
        margin = rx - distance
        if margin > best_margin:
            best_margin = margin
            best = (mast, distance, rx)
    assert best is not None
    return best


def _add_mast_block(doc, record: LightningRecord, mast: LightningArresterMast) -> None:
    zone = record.zone_type
    h = mast.height_h_m
    h0, r0, _ = single_rod_zone(h, 0.0, zone)
    _, _, rx_eaves = single_rod_zone(h, record.eaves_height_m, zone)
    _, _, rx_ridge = single_rod_zone(h, record.ridge_height_m, zone)
    add_paragraph(doc, f"Мачта {mast.mast_id} (h = {fmt(h)} м, {ZONE_LABELS[zone]})", bold=True)
    if zone == LightningZoneType.ZONE_A:
        h0_coeff = ZONE_A_H0_COEFF
        k_r = ZONE_A_R0_BASE - ZONE_A_R0_SLOPE * h
        h0_formula = "h_{0} = 0.85 · h"
        r0_formula = "r_{0} = (1.1 − 0.002 · h) · h"
        r0_substitution = (
            f"r_{{0}} = (1.1 − 0.002 · {fmt(h)}) · {fmt(h)} = {fmt(k_r, 4)} · {fmt(h)} = {fmt(r0)} м"
        )
    else:
        h0_coeff = ZONE_B_H0_COEFF
        h0_formula = "h_{0} = 0.92 · h"
        r0_formula = "r_{0} = 1.5 · h"
        r0_substitution = f"r_{{0}} = 1.5 · {fmt(h)} = {fmt(r0)} м"
    add_step(
        doc,
        "Высота вершины конуса защиты",
        h0_formula,
        f"h_{{0}} = {fmt(h0_coeff)} · {fmt(h)} = {fmt(h0)} м",
        f"вершина конуса защиты на высоте {fmt(h0)} м",
    )
    add_step(
        doc,
        "Радиус защиты на уровне земли",
        r0_formula,
        r0_substitution,
        f"r_{{0}} = {fmt(r0)} м",
    )
    for label, hx, rx in (
        ("карниза", record.eaves_height_m, rx_eaves),
        ("конька кровли", record.ridge_height_m, rx_ridge),
    ):
        if zone == LightningZoneType.ZONE_A:
            rx_formula = "r_{x} = (1.1 − 0.002 · h) · (h − h_{x} / 0.85), при h_{x} < h_{0}"
            if hx >= h0:
                rx_substitution = f"h_{{x}} = {fmt(hx)} м ≥ h_{{0}} = {fmt(h0)} м, поэтому r_{{x}} = 0.00 м"
            else:
                rx_substitution = (
                    f"r_{{x}} = {fmt(k_r, 4)} · ({fmt(h)} − {fmt(hx)} / 0.85) = {fmt(k_r, 4)} · "
                    f"{fmt(h - hx / ZONE_A_H0_COEFF, 4)} = {fmt(rx)} м"
                )
        else:
            rx_formula = "r_{x} = 1.5 · (h − h_{x} / 0.92), при h_{x} < h_{0}"
            if hx >= h0:
                rx_substitution = f"h_{{x}} = {fmt(hx)} м ≥ h_{{0}} = {fmt(h0)} м, поэтому r_{{x}} = 0.00 м"
            else:
                rx_substitution = (
                    f"r_{{x}} = 1.5 · ({fmt(h)} − {fmt(hx)} / 0.92) = 1.5 · {fmt(h - hx / ZONE_B_H0_COEFF, 4)} = "
                    f"{fmt(rx)} м"
                )
        add_step(
            doc,
            f"Радиус защиты на высоте {label} (h_{{x}} = {fmt(hx)} м)",
            rx_formula,
            rx_substitution,
            f"r_{{x}} = {fmt(rx)} м на высоте {label}",
        )
    distance_to_walls = distance_to_building(
        mast.x_m, mast.y_m, record.storage_length_m, record.storage_width_m
    )
    add_step(
        doc,
        "Расстояние от мачты до стен хранилища",
        "d_{стен} ≥ 5.00 м (задание № 4 к п. 8.1.1 СП РК 2.04-103-2013)",
        f"d_{{стен}} = {fmt(distance_to_walls)} м",
        "расстояние достаточно" if distance_to_walls >= 5.0 else "расстояние меньше 5.00 м",
        ok=distance_to_walls >= 5.0,
    )


def add_section_7(doc, project: WarehouseProjectInput, lightning_records: list[LightningRecord]) -> None:
    add_heading(doc, "7. Расчет зон молниезащиты хранилищ ВМ (СН РК 2.04-02-2011 / СП РК 2.04-103-2013, Раздел 8, п. 8.1.1)", level=1)
    storages = storage_index(project)
    rows: list[list[str]] = []
    red_rows: set[int] = set()
    for record in lightning_records:
        name = storages[record.storage_id].name
        add_paragraph(
            doc,
            f"Хранилище «{name}»: {ZONE_LABELS[record.zone_type]}, карниз {fmt(record.eaves_height_m)} м, "
            f"конек {fmt(record.ridge_height_m)} м, L = {fmt(record.storage_length_m)} м, W = {fmt(record.storage_width_m)} м",
            bold=True,
        )
        for mast in record.masts:
            _add_mast_block(doc, record, mast)
        add_violations(doc, record.result.violations)
        checkpoints = generate_storage_checkpoints_3d(
            record.storage_length_m, record.storage_width_m, record.eaves_height_m, record.ridge_height_m
        )
        for point in checkpoints:
            mast, distance, rx = _best_mast(point, record.masts, record.zone_type)
            inside = rx > 0.0 and distance <= rx
            if not inside:
                red_rows.add(len(rows))
            rows.append(
                [
                    name,
                    point.name,
                    fmt(point.z_height_m),
                    mast.mast_id,
                    fmt(distance),
                    fmt(rx),
                    "Внутри зоны защиты" if inside else "Вне зоны защиты",
                ]
            )
        result = record.result
        min_height = result.min_recommended_mast_height_m
        add_step(
            doc,
            "Минимальная высота мачты для покрытия всех точек",
            "h_{min}: все контрольные точки (x_{i}, y_{i}, h_{i}) с d_{i} ≤ r_{x}(h_{i})",
            f"подбор бисекцией с шагом 0.1 м: h_{{min}} = {fmt(min_height) if min_height is not None else '—'} м",
            "все точки здания покрыты зоной защиты"
            if result.is_fully_protected
            else f"не покрыты точки: {', '.join(result.unprotected_points) or 'нарушения размещения мачт'}",
            ok=result.is_fully_protected,
        )
    add_paragraph(doc, "Таблица 7.1 — Проверка вхождения контрольных точек кровли и вентшахт в конус молниезащиты", bold=True)
    add_table(
        doc,
        ["Хранилище", "Контрольная точка", "h_x, м", "Мачта", "d, м", "r_x, м", "Статус"],
        rows,
        red_rows=frozenset(red_rows),
    )
