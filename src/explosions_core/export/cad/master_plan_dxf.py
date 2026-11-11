"""Чертеж № 2: генеральный план склада ВМ и ситуационная схема безопасных расстояний (r_д и R_увв).

Ограда, запретная зона, зона запрета огня, караульное помещение и навес для тары строятся по проектным
расстояниям; если расстояние не задано — по нормативному минимуму для типа склада (`calc.site_plan`).
"""

import math
from pathlib import Path

from explosions_core.calc.geometry import (
    nearest_point,
    offset_bounds,
    storage_center,
    storage_key,
    storages_bounds,
)
from explosions_core.calc.safe_distances import calculate_explosive_mass
from explosions_core.calc.site_plan import SitePlanDistances, site_plan_distances
from explosions_core.domain import (
    BermDesignResult,
    DetonationPairResult,
    StorageBuilding,
    UVVDistanceResult,
    WarehouseProjectInput,
)
from explosions_core.export.cad.dxf_styles import (
    LAYER_BERM_CREST,
    LAYER_BERM_TOE,
    LAYER_DIMENSIONS,
    LAYER_PERIMETER,
    LAYER_SAFE_RD,
    LAYER_SAFE_UVV,
    LAYER_WALLS,
    TEXT_HEIGHT_M,
    TITLE_TEXT_HEIGHT_M,
    add_aligned_dimension,
    add_circle,
    add_mtext,
    add_rectangle,
    add_text,
    create_document,
    draw_table,
    save_document,
)
from explosions_core.norms.references import DRAWING_CLAUSE_DETONATION

# Условные размеры и положение объектов на схеме (оформление чертежа, не нормативы)
PRP_HALF_LENGTH_M = 10.0
PRP_HALF_WIDTH_M = 5.0
PRP_SCHEMATIC_GAP_FROM_FENCE_M = 25.0
GUARDHOUSE_HALF_SIZE_M = 3.0
TARE_HALF_SIZE_M = 4.0
TARGET_MARK_HALF_SIZE_M = 2.0
LABEL_OFFSET_M = 1.0
TABLE_ROW_HEIGHT_M = 2.0
TABLE_GAP_M = 10.0
TABLE_COLUMN_WIDTHS_M = [8.0, 6.0, 8.0, 8.0]
DEFAULT_BEARING_STEP_DEG = 360.0


def export_master_plan_dxf(
    project_input: WarehouseProjectInput,
    detonation_results: list[DetonationPairResult],
    uvv_results: list[UVVDistanceResult],
    berm_results: dict[str, BermDesignResult],
    output_path: Path,
) -> Path:
    doc = create_document()
    msp = doc.modelspace()

    storages = [item for item in project_input.storages if item.x_m is not None and item.y_m is not None]
    storages_by_id = {storage_key(item): item for item in storages}
    distances = site_plan_distances(project_input)

    _draw_storages(msp, storages, berm_results)
    _draw_detonation_zones(msp, storages_by_id, detonation_results)
    fence, bottom_y = _draw_perimeter(msp, storages, distances)
    _draw_uvv_zones(msp, storages_by_id, uvv_results)
    _draw_external_targets(msp, project_input, fence)
    _draw_fixed_objects(msp, fence, distances, has_prp=project_input.unloading_platform is not None)
    _draw_summary_table(msp, (fence[0], bottom_y - TABLE_GAP_M), detonation_results, uvv_results)

    return save_document(doc, output_path)


def _draw_storages(msp, storages: list[StorageBuilding], berm_results: dict[str, BermDesignResult]) -> None:
    for storage in storages:
        x1, y1 = storage.x_m, storage.y_m
        x2, y2 = x1 + storage.length_m, y1 + storage.width_m
        add_rectangle(msp, x1, y1, x2, y2, LAYER_WALLS)
        berm = berm_results.get(storage_key(storage))
        if berm is not None:
            _draw_storage_berm(msp, (x1, y1, x2, y2), berm)
        groups = ", ".join(sorted({item.group.value for item in storage.items})) or "—"
        mass_t = calculate_explosive_mass(storage.items) / 1000.0
        center_x, _ = storage_center(storage)
        add_text(
            msp,
            f"{storage.name}: Q = {mass_t:.2f} т ВВ, группы: {groups}",
            (center_x, y2 + LABEL_OFFSET_M),
            LAYER_DIMENSIONS,
        )


def _draw_storage_berm(msp, bounds: tuple[float, float, float, float], berm: BermDesignResult) -> None:
    x1, y1, x2, y2 = bounds
    total_offset_x = (berm.outer_footprint_length_m - (x2 - x1)) / 2.0
    total_offset_y = (berm.outer_footprint_width_m - (y2 - y1)) / 2.0
    run = (berm.base_width_m - berm.crest_width_m) / 2.0
    clearance_x = total_offset_x - berm.base_width_m
    clearance_y = total_offset_y - berm.base_width_m
    rings = [
        (total_offset_x, total_offset_y, LAYER_BERM_TOE),
        (total_offset_x - run, total_offset_y - run, LAYER_BERM_CREST),
        (total_offset_x - run - berm.crest_width_m, total_offset_y - run - berm.crest_width_m, LAYER_BERM_CREST),
        (clearance_x, clearance_y, LAYER_BERM_TOE),
    ]
    for offset_x, offset_y, layer in rings:
        add_rectangle(msp, x1 - offset_x, y1 - offset_y, x2 + offset_x, y2 + offset_y, layer)


def _draw_detonation_zones(
    msp,
    storages_by_id: dict[str, StorageBuilding],
    detonation_results: list[DetonationPairResult],
) -> None:
    for result in detonation_results:
        storage_i = storages_by_id[result.storage_i_id]
        storage_j = storages_by_id[result.storage_j_id]
        center_i = storage_center(storage_i)
        center_j = storage_center(storage_j)
        add_circle(msp, center_i, result.r_d_i_to_j_m, LAYER_SAFE_RD)
        add_circle(msp, center_j, result.r_d_j_to_i_m, LAYER_SAFE_RD)
        if result.is_safe:
            relation = ">="
            status = ""
        else:
            relation = "<"
            status = " НАРУШЕНИЕ"
        add_aligned_dimension(
            msp,
            nearest_point(storage_i, storage_j),
            nearest_point(storage_j, storage_i),
            distance=LABEL_OFFSET_M,
            text=(
                f"L_факт = {result.actual_clear_distance_m:.2f} м {relation} "
                f"r_д = {result.governing_required_r_d_m:.2f} м ({DRAWING_CLAUSE_DETONATION}){status}"
            ),
        )


def _draw_perimeter(
    msp,
    storages: list[StorageBuilding],
    distances: SitePlanDistances,
) -> tuple[tuple[float, float, float, float], float]:
    """Ограда, запретная зона и зона запрета огня; возвращает контур ограды и нижнюю отметку зон."""
    building_zone = storages_bounds(storages)
    fence = offset_bounds(building_zone, distances.fence_to_storage_m)
    add_rectangle(msp, *fence, LAYER_PERIMETER)
    bottoms = [fence[1]]
    if distances.forbidden_zone_width_m is not None:
        zone = offset_bounds(fence, distances.forbidden_zone_width_m)
        add_rectangle(msp, *zone, LAYER_PERIMETER)
        bottoms.append(zone[1])
    fire = offset_bounds(building_zone, distances.open_fire_ban_radius_m)
    add_rectangle(msp, *fire, LAYER_PERIMETER)
    bottoms.append(fire[1])
    return fence, min(bottoms)


def _draw_uvv_zones(
    msp,
    storages_by_id: dict[str, StorageBuilding],
    uvv_results: list[UVVDistanceResult],
) -> None:
    for result in uvv_results:
        storage = storages_by_id.get(result.storage_id)
        if storage is None:
            continue
        add_circle(msp, storage_center(storage), result.required_distance_m, LAYER_SAFE_UVV)


def _draw_external_targets(
    msp,
    project_input: WarehouseProjectInput,
    fence: tuple[float, float, float, float],
) -> None:
    fence_center = ((fence[0] + fence[2]) / 2.0, (fence[1] + fence[3]) / 2.0)
    targets = project_input.external_targets
    for index, target in enumerate(targets):
        bearing = target.bearing_deg
        if bearing is None:
            bearing = index * DEFAULT_BEARING_STEP_DEG / max(len(targets), 1)
        angle = math.radians(bearing)
        target_x = fence_center[0] + target.actual_distance_m * math.cos(angle)
        target_y = fence_center[1] + target.actual_distance_m * math.sin(angle)
        add_rectangle(
            msp,
            target_x - TARGET_MARK_HALF_SIZE_M,
            target_y - TARGET_MARK_HALF_SIZE_M,
            target_x + TARGET_MARK_HALF_SIZE_M,
            target_y + TARGET_MARK_HALF_SIZE_M,
            LAYER_SAFE_UVV,
        )
        add_text(
            msp,
            f"{target.name} ({target.actual_distance_m:.1f} м)",
            (target_x + TARGET_MARK_HALF_SIZE_M, target_y + TARGET_MARK_HALF_SIZE_M),
            LAYER_DIMENSIONS,
        )


def _draw_fixed_objects(
    msp,
    fence: tuple[float, float, float, float],
    distances: SitePlanDistances,
    *,
    has_prp: bool,
) -> None:
    fx1, fy1, fx2, fy2 = fence
    guard_x = fx2 + distances.fence_to_guardhouse_m
    guard_y = fy1
    add_rectangle(
        msp,
        guard_x,
        guard_y,
        guard_x + GUARDHOUSE_HALF_SIZE_M * 2.0,
        guard_y + GUARDHOUSE_HALF_SIZE_M * 2.0,
        LAYER_PERIMETER,
    )
    add_text(msp, "Караульное помещение", (guard_x, guard_y + GUARDHOUSE_HALF_SIZE_M * 2.0 + LABEL_OFFSET_M), LAYER_DIMENSIONS)

    if distances.fence_to_tare_storage_m is not None:
        tare_x = fx1 - distances.fence_to_tare_storage_m - TARE_HALF_SIZE_M * 2.0
        tare_y = fy2 - TARE_HALF_SIZE_M * 2.0
        add_rectangle(msp, tare_x, tare_y, tare_x + TARE_HALF_SIZE_M * 2.0, tare_y + TARE_HALF_SIZE_M * 2.0, LAYER_PERIMETER)
        add_text(msp, "Склад тары", (tare_x, tare_y - LABEL_OFFSET_M), LAYER_DIMENSIONS)

    if has_prp:
        prp_x = fx1 - PRP_HALF_LENGTH_M * 2.0 - PRP_SCHEMATIC_GAP_FROM_FENCE_M
        prp_y = fy1
        add_rectangle(msp, prp_x, prp_y, prp_x + PRP_HALF_LENGTH_M * 2.0, prp_y + PRP_HALF_WIDTH_M * 2.0, LAYER_PERIMETER)
        add_text(msp, "ПРП (схематично)", (prp_x, prp_y - LABEL_OFFSET_M), LAYER_DIMENSIONS)


def _draw_summary_table(
    msp,
    origin: tuple[float, float],
    detonation_results: list[DetonationPairResult],
    uvv_results: list[UVVDistanceResult],
) -> None:
    rows: list[list[str]] = [["Параметр", "Требуется, м", "Факт, м", "Статус"]]
    for result in detonation_results:
        rows.append(
            [
                f"r_д {result.storage_i_id}-{result.storage_j_id}",
                f"{result.governing_required_r_d_m:.2f}",
                f"{result.actual_clear_distance_m:.2f}",
                "OK" if result.is_safe else "НАРУШЕНИЕ",
            ]
        )
    for result in uvv_results:
        rows.append(
            [
                f"R_увв {result.storage_id}-{result.object_id}",
                f"{result.required_distance_m:.2f}",
                f"{result.actual_distance_m:.2f}",
                "OK" if result.is_safe else "НАРУШЕНИЕ",
            ]
        )
    draw_table(msp, origin, TABLE_COLUMN_WIDTHS_M, rows, TABLE_ROW_HEIGHT_M, LAYER_DIMENSIONS, text_height=TEXT_HEIGHT_M)
    add_mtext(
        msp,
        "ВЕДОМОСТЬ БЕЗОПАСНЫХ РАССТОЯНИЙ (Приказ № 343, Прил. 11)",
        (origin[0], origin[1] + TABLE_ROW_HEIGHT_M),
        LAYER_DIMENSIONS,
        char_height=TITLE_TEXT_HEIGHT_M / 2.0,
    )
