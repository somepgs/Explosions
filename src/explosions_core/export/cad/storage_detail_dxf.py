"""Чертеж № 1: детальный технологический план хранилища ВМ, обвалования и молниезащиты."""

from pathlib import Path

from explosions_core.export.cad.dxf_styles import (
    LAYER_AISLES,
    LAYER_BERM_CREST,
    LAYER_BERM_TOE,
    LAYER_DIMENSIONS,
    LAYER_LIGHTNING,
    LAYER_RACKS,
    LAYER_WALLS,
    MAST_MARK_RADIUS_M,
    TEXT_HEIGHT_M,
    TITLE_TEXT_HEIGHT_M,
    WALL_THICKNESS_M,
    add_circle,
    add_cross_marker,
    add_filled_circle,
    add_linear_dimension,
    add_mtext,
    add_polyline,
    add_rectangle,
    add_text,
    create_document,
    draw_slope_berm_ticks,
    save_document,
)
from explosions_core.domain import (
    BermDesignInput,
    BermDesignResult,
    LightningArresterMast,
    LightningProtectionResult,
    StorageMethod,
    StorageSizingInput,
    StorageSizingResult,
)

DIM_STEP_M = 2.0
STAMP_GAP_M = 6.0
MAST_LABEL_OFFSET_M = 0.6


def export_storage_detail_dxf(
    sizing_input: StorageSizingInput,
    sizing_result: StorageSizingResult,
    berm_input: BermDesignInput,
    berm_result: BermDesignResult,
    lightning_masts: list[LightningArresterMast],
    lightning_result: LightningProtectionResult,
    output_path: Path,
) -> Path:
    doc = create_document()
    msp = doc.modelspace()

    half_length = sizing_result.min_internal_length_m / 2.0
    half_width = sizing_result.min_internal_width_m / 2.0
    driveway_half = berm_input.entrance_opening_width_m / 2.0 if berm_input.has_entrance_screen_berm else 0.0
    gate_half = min(berm_input.entrance_opening_width_m / 2.0, half_width)

    _draw_walls(msp, half_length, half_width, gate_half)
    _draw_racks_and_stacks(msp, sizing_input, sizing_result, half_length, half_width)
    _draw_berm(msp, berm_input, berm_result, half_length, half_width, driveway_half)
    if driveway_half > 0.0 and berm_result.screen_berm_length_m > 0.0:
        _draw_screen_berm(msp, berm_input, berm_result, half_length)
    _draw_lightning(msp, lightning_masts, lightning_result)
    _draw_dimensions(msp, sizing_input, sizing_result, berm_input, berm_result, half_length, half_width)
    _draw_stamp(msp, sizing_input, sizing_result, berm_input, berm_result, lightning_result, half_length, half_width)

    return save_document(doc, output_path)


def _draw_walls(msp, half_length: float, half_width: float, gate_half: float) -> None:
    add_rectangle(msp, -half_length, -half_width, half_length, half_width, LAYER_WALLS)
    outer_length = half_length + WALL_THICKNESS_M
    outer_width = half_width + WALL_THICKNESS_M
    add_polyline(
        msp,
        [
            (-outer_length, gate_half),
            (-outer_length, outer_width),
            (outer_length, outer_width),
            (outer_length, -outer_width),
            (-outer_length, -outer_width),
            (-outer_length, -gate_half),
        ],
        LAYER_WALLS,
    )


def _row_layout(sizing_input: StorageSizingInput, sizing_result: StorageSizingResult) -> list[tuple[str, float]]:
    is_rack = sizing_input.storage_method == StorageMethod.RACK
    wall_count = sizing_input.wall_racks_count if is_rack else 0
    wall_row = ("wall", sizing_result.wall_rack_depth_m)
    island_rows = [("island", sizing_result.island_line_depth_m)] * sizing_input.island_rows_count
    if wall_count == 0:
        return island_rows
    rest_walls = [wall_row] * (wall_count - 1)
    return [wall_row] + island_rows + rest_walls


def _draw_racks_and_stacks(
    msp,
    sizing_input: StorageSizingInput,
    sizing_result: StorageSizingResult,
    half_length: float,
    half_width: float,
) -> None:
    clearance = sizing_input.wall_clearance_m
    aisle = sizing_result.required_aisle_width_m
    spec = sizing_input.unit_spec
    method_name = "стеллаж" if sizing_input.storage_method == StorageMethod.RACK else "штабель"

    line_length = sizing_result.line_length_m
    line_x1 = -line_length / 2.0
    line_x2 = line_length / 2.0
    inner_x1 = -half_length + clearance
    inner_x2 = half_length - clearance
    inner_y1 = -half_width + clearance
    inner_y2 = half_width - clearance

    rows = _row_layout(sizing_input, sizing_result)
    y = inner_y1
    for index, (kind, depth) in enumerate(rows):
        y1, y2 = y, y + depth
        add_rectangle(msp, line_x1, y1, line_x2, y2, LAYER_RACKS)
        _draw_unit_columns(msp, line_x1, y1, y2, sizing_result.units_along_line, spec.length_m, spec.unit_gap_m)
        if kind == "island":
            mid_y = y1 + spec.width_m + spec.unit_gap_m / 2.0
            add_polyline(msp, [(line_x1, mid_y), (line_x2, mid_y)], LAYER_RACKS)
        label = (
            f"Л{index + 1}: {method_name}, ярусов/полок {sizing_result.shelves_or_tiers_count}, "
            f"H = {sizing_result.total_loaded_height_m:.2f} м"
        )
        add_mtext(msp, label, (line_x2 + 0.2, (y1 + y2) / 2.0), LAYER_RACKS, char_height=TEXT_HEIGHT_M)
        y = y2
        if index < len(rows) - 1:
            add_rectangle(msp, inner_x1, y, inner_x2, y + aisle, LAYER_AISLES)
            y += aisle

    add_rectangle(msp, inner_x1, inner_y1, line_x1, inner_y2, LAYER_AISLES)
    add_rectangle(msp, line_x2, inner_y1, inner_x2, inner_y2, LAYER_AISLES)


def _draw_unit_columns(
    msp,
    x1: float,
    y1: float,
    y2: float,
    units_along_line: int,
    unit_length: float,
    unit_gap: float,
) -> None:
    pitch = unit_length + unit_gap
    for column in range(1, units_along_line):
        x = x1 + column * pitch - unit_gap / 2.0
        add_polyline(msp, [(x, y1), (x, y2)], LAYER_RACKS)


def _berm_rings(
    berm_input: BermDesignInput,
    berm_result: BermDesignResult,
    half_length: float,
    half_width: float,
) -> dict[str, float]:
    run = (berm_result.base_width_m - berm_result.crest_width_m) / 2.0
    toe_inner_length = half_length + WALL_THICKNESS_M + berm_input.wall_to_inner_toe_clearance_m
    toe_inner_width = half_width + WALL_THICKNESS_M + berm_input.wall_to_inner_toe_clearance_m
    crest_inner_length = toe_inner_length + run
    crest_inner_width = toe_inner_width + run
    crest_outer_length = crest_inner_length + berm_result.crest_width_m
    crest_outer_width = crest_inner_width + berm_result.crest_width_m
    toe_outer_length = toe_inner_length + berm_result.base_width_m
    toe_outer_width = toe_inner_width + berm_result.base_width_m
    return {
        "run": run,
        "toe_inner_length": toe_inner_length,
        "toe_inner_width": toe_inner_width,
        "crest_inner_length": crest_inner_length,
        "crest_inner_width": crest_inner_width,
        "crest_outer_length": crest_outer_length,
        "crest_outer_width": crest_outer_width,
        "toe_outer_length": toe_outer_length,
        "toe_outer_width": toe_outer_width,
    }


def _draw_berm(
    msp,
    berm_input: BermDesignInput,
    berm_result: BermDesignResult,
    half_length: float,
    half_width: float,
    driveway_half: float,
) -> None:
    rings = _berm_rings(berm_input, berm_result, half_length, half_width)
    run = rings["run"]

    _draw_ring(msp, rings["toe_inner_length"], rings["toe_inner_width"], driveway_half, LAYER_BERM_TOE)
    _draw_ring(msp, rings["crest_inner_length"], rings["crest_inner_width"], driveway_half, LAYER_BERM_CREST)
    _draw_ring(msp, rings["crest_outer_length"], rings["crest_outer_width"], driveway_half, LAYER_BERM_CREST)
    _draw_ring(msp, rings["toe_outer_length"], rings["toe_outer_width"], driveway_half, LAYER_BERM_TOE)

    _draw_ring_slope(
        msp,
        rings["crest_inner_length"],
        rings["crest_inner_width"],
        -run,
        driveway_half,
    )
    _draw_ring_slope(
        msp,
        rings["crest_outer_length"],
        rings["crest_outer_width"],
        run,
        driveway_half,
    )


def _draw_ring(msp, half_length: float, half_width: float, driveway_half: float, layer: str) -> None:
    if driveway_half <= 0.0:
        add_rectangle(msp, -half_length, -half_width, half_length, half_width, layer)
        return
    add_polyline(
        msp,
        [
            (-half_length, driveway_half),
            (-half_length, half_width),
            (half_length, half_width),
            (half_length, -half_width),
            (-half_length, -half_width),
            (-half_length, -driveway_half),
        ],
        layer,
    )


def _ring_sides(
    crest_length: float,
    crest_width: float,
    run: float,
    driveway_half: float,
) -> list[tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]]:
    lc, wc = crest_length, crest_width
    sides = [
        ((-lc, wc), (lc, wc), (-lc, wc + run), (lc, wc + run)),
        ((lc, wc), (lc, -wc), (lc + run, wc), (lc + run, -wc)),
        ((lc, -wc), (-lc, -wc), (lc, -wc - run), (-lc, -wc - run)),
    ]
    if driveway_half > 0.0:
        sides.append(((-lc, driveway_half), (-lc, wc), (-lc - run, driveway_half), (-lc - run, wc)))
        sides.append(((-lc, -wc), (-lc, -driveway_half), (-lc - run, -wc), (-lc - run, -driveway_half)))
    else:
        sides.append(((-lc, wc), (-lc, -wc), (-lc - run, wc), (-lc - run, -wc)))
    return sides


def _draw_ring_slope(msp, crest_length: float, crest_width: float, run: float, driveway_half: float) -> None:
    for crest_p1, crest_p2, toe_p1, toe_p2 in _ring_sides(crest_length, crest_width, run, driveway_half):
        draw_slope_berm_ticks(msp, crest_p1, crest_p2, toe_p1, toe_p2)


def _draw_screen_berm(
    msp,
    berm_input: BermDesignInput,
    berm_result: BermDesignResult,
    half_length: float,
) -> None:
    run = (berm_result.base_width_m - berm_result.crest_width_m) / 2.0
    toe_outer_edge_x = -(half_length + WALL_THICKNESS_M + berm_input.wall_to_inner_toe_clearance_m + berm_result.base_width_m)
    crest_inner_x = toe_outer_edge_x - run
    crest_outer_x = crest_inner_x - berm_result.crest_width_m
    toe_far_x = toe_outer_edge_x - berm_result.base_width_m
    half_span = berm_result.screen_berm_length_m / 2.0

    add_rectangle(msp, crest_outer_x, -half_span, crest_inner_x, half_span, LAYER_BERM_CREST)
    add_rectangle(msp, toe_far_x, -half_span, toe_outer_edge_x, half_span, LAYER_BERM_TOE)
    draw_slope_berm_ticks(msp, (crest_inner_x, -half_span), (crest_inner_x, half_span), (toe_outer_edge_x, -half_span), (toe_outer_edge_x, half_span))
    draw_slope_berm_ticks(msp, (crest_outer_x, -half_span), (crest_outer_x, half_span), (toe_far_x, -half_span), (toe_far_x, half_span))


def _draw_lightning(
    msp,
    masts: list[LightningArresterMast],
    result: LightningProtectionResult,
) -> None:
    rings_by_id = {str(item["mast_id"]): item for item in result.mast_results}
    for mast in masts:
        center = (mast.x_m, mast.y_m)
        add_cross_marker(msp, center, MAST_MARK_RADIUS_M * 2.0, LAYER_LIGHTNING)
        add_filled_circle(msp, center, MAST_MARK_RADIUS_M, LAYER_LIGHTNING)
        add_text(
            msp,
            f"{mast.mast_id} (h = {mast.height_h_m:.1f} м)",
            (mast.x_m + MAST_LABEL_OFFSET_M, mast.y_m + MAST_LABEL_OFFSET_M),
            LAYER_LIGHTNING,
        )
        ring = rings_by_id.get(mast.mast_id)
        if ring is None:
            continue
        for key in ("r0_ground_m", "rx_at_eaves_m", "rx_at_ridge_m"):
            radius = float(ring[key])
            if radius > 0.0:
                add_circle(msp, center, radius, LAYER_LIGHTNING)


def _first_aisle_y(sizing_input: StorageSizingInput, sizing_result: StorageSizingResult, half_width: float) -> float | None:
    rows = _row_layout(sizing_input, sizing_result)
    if len(rows) < 2:
        return None
    return -half_width + sizing_input.wall_clearance_m + rows[0][1]


def _draw_dimensions(
    msp,
    sizing_input: StorageSizingInput,
    sizing_result: StorageSizingResult,
    berm_input: BermDesignInput,
    berm_result: BermDesignResult,
    half_length: float,
    half_width: float,
) -> None:
    rings = _berm_rings(berm_input, berm_result, half_length, half_width)
    extent_x = rings["toe_outer_length"]
    extent_y = rings["toe_outer_width"]

    add_linear_dimension(
        msp,
        (-half_length, -half_width),
        (half_length, -half_width),
        (0.0, -extent_y - DIM_STEP_M),
    )
    add_linear_dimension(
        msp,
        (half_length, -half_width),
        (half_length, half_width),
        (extent_x + DIM_STEP_M, 0.0),
        angle=90.0,
    )

    aisle_y = _first_aisle_y(sizing_input, sizing_result, half_width)
    if aisle_y is not None:
        add_linear_dimension(
            msp,
            (0.0, aisle_y),
            (0.0, aisle_y + sizing_result.required_aisle_width_m),
            (extent_x + 2.0 * DIM_STEP_M, 0.0),
            angle=90.0,
            text=f"{sizing_result.required_aisle_width_m:.2f}",
        )

    add_linear_dimension(
        msp,
        (-half_length, -half_width),
        (-half_length, -half_width + sizing_input.wall_clearance_m),
        (-extent_x - DIM_STEP_M, 0.0),
        angle=90.0,
        text=f"{sizing_input.wall_clearance_m:.2f}",
    )
    add_linear_dimension(
        msp,
        (-rings["crest_inner_length"], 0.0),
        (-rings["crest_outer_length"], 0.0),
        (0.0, -extent_y - 2.0 * DIM_STEP_M),
        text=f"{berm_result.crest_width_m:.2f}",
    )
    add_linear_dimension(
        msp,
        (-rings["toe_inner_length"], 0.0),
        (-rings["toe_outer_length"], 0.0),
        (0.0, -extent_y - 3.0 * DIM_STEP_M),
        text=f"{berm_result.base_width_m:.2f}",
    )


def _draw_stamp(
    msp,
    sizing_input: StorageSizingInput,
    sizing_result: StorageSizingResult,
    berm_input: BermDesignInput,
    berm_result: BermDesignResult,
    lightning_result: LightningProtectionResult,
    half_length: float,
    half_width: float,
) -> None:
    rings = _berm_rings(berm_input, berm_result, half_length, half_width)
    stamp_x = rings["toe_outer_length"] + STAMP_GAP_M
    text = "\n".join(
        [
            "ЭКСПЛИКАЦИЯ ПАРАМЕТРОВ",
            f"Внутр. длина L = {sizing_result.min_internal_length_m:.2f} м",
            f"Внутр. ширина W = {sizing_result.min_internal_width_m:.2f} м",
            f"Ширина прохода = {sizing_result.required_aisle_width_m:.2f} м (п. 579-580 Приказа № 343)",
            f"Отступ от стен = {sizing_input.wall_clearance_m:.2f} м (п. 579)",
            f"Высота укладки H = {sizing_result.total_loaded_height_m:.2f} м (п. 579-580)",
            f"Высота обвалования H_в = {berm_result.berm_height_m:.2f} м (п. 602-607)",
            f"Ширина гребня = {berm_result.crest_width_m:.2f} м (п. 602-607)",
            f"Ширина подошвы = {berm_result.base_width_m:.2f} м (п. 602-607)",
            f"Молниезащита: {lightning_result.zone_type.value} (СП РК 2.04-103-2013, п. 8.1.1)",
        ]
    )
    add_mtext(msp, text, (stamp_x, half_width), LAYER_DIMENSIONS, char_height=TITLE_TEXT_HEIGHT_M / 2.0)
