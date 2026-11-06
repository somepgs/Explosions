"""Расчет геометрии защитного обвалования хранилищ ВМ по п. 602-607 Приказа МИР РК № 343 (в ред. Приказа МЧС РК № 120)."""

import math

from explosions_core.domain import (
    BermDesignInput,
    BermDesignResult,
    BermSoilMaterial,
    NormativeViolation,
)
from explosions_core.norms.constants_rk343 import (
    MAX_WALL_TO_BERM_TOE_DIST_M,
    MIN_BERM_CREST_WIDTH_M,
    MIN_WALL_TO_BERM_TOE_DIST_M,
)
from explosions_core.norms.references import CLAUSE_BERM, CLAUSE_BERM_SOIL

FORBIDDEN_BERM_SOIL = (BermSoilMaterial.STONE_OR_GRAVEL, BermSoilMaterial.COMBUSTIBLE_MATERIAL)


def calculate_berm_design(data: BermDesignInput) -> BermDesignResult:
    violations: list[NormativeViolation] = []

    if data.soil_material in FORBIDDEN_BERM_SOIL:
        violations.append(
            NormativeViolation(
                code="BERM_INVALID_SOIL_MATERIAL",
                clause=CLAUSE_BERM_SOIL,
                description="Для обвалования запрещено применять камень, щебень, горючие материалы и угольную мелочь",
                actual_value=data.soil_material.value,
                required_value="plastic_clay_loam или sandy_free_flowing",
            )
        )
    if data.crest_width_m < MIN_BERM_CREST_WIDTH_M:
        violations.append(
            NormativeViolation(
                code="BERM_CREST_WIDTH_TOO_SMALL",
                clause=CLAUSE_BERM,
                description="Ширина вала по гребню меньше нормативной",
                actual_value=data.crest_width_m,
                required_value=MIN_BERM_CREST_WIDTH_M,
            )
        )
    if data.crest_elevation_above_eaves_m < 0.0:
        violations.append(
            NormativeViolation(
                code="BERM_CREST_ELEVATION_NEGATIVE",
                clause=CLAUSE_BERM,
                description="Гребень вала не может быть ниже карниза здания",
                actual_value=data.crest_elevation_above_eaves_m,
                required_value=0.0,
            )
        )
    if data.wall_to_inner_toe_clearance_m < MIN_WALL_TO_BERM_TOE_DIST_M:
        violations.append(
            NormativeViolation(
                code="BERM_TOE_TOO_CLOSE_TO_WALL",
                clause=CLAUSE_BERM,
                description="Внутренняя подошва вала расположена ближе минимума для водоотводной канавы",
                actual_value=data.wall_to_inner_toe_clearance_m,
                required_value=MIN_WALL_TO_BERM_TOE_DIST_M,
            )
        )
    if data.wall_to_inner_toe_clearance_m > MAX_WALL_TO_BERM_TOE_DIST_M:
        violations.append(
            NormativeViolation(
                code="BERM_TOE_TOO_FAR_FROM_WALL",
                clause=CLAUSE_BERM,
                description="Внутренняя подошва вала расположена дальше рекомендуемого максимума от стены",
                actual_value=data.wall_to_inner_toe_clearance_m,
                required_value=MAX_WALL_TO_BERM_TOE_DIST_M,
            )
        )

    berm_height = data.eaves_height_m + data.crest_elevation_above_eaves_m
    if berm_height <= 0.0:
        raise ValueError(
            f"Высота вала H_в = {berm_height:.2f} м должна быть больше нуля; проверьте высоту карниза и превышение гребня"
        )
    tan_slope = math.tan(math.radians(data.natural_slope_angle_deg))
    base_width = data.crest_width_m + 2.0 * berm_height / tan_slope
    cross_section_area = 0.5 * (data.crest_width_m + base_width) * berm_height

    offset_to_centerline = data.wall_to_inner_toe_clearance_m + base_width / 2.0
    perimeter_centerline = 2.0 * (data.storage_length_m + data.storage_width_m) + 8.0 * offset_to_centerline
    main_length = max(0.0, perimeter_centerline - data.entrance_opening_width_m)

    if data.has_entrance_screen_berm:
        screen_length = data.entrance_opening_width_m + 2.0 * data.screen_overlap_each_side_m
    else:
        screen_length = 0.0

    total_volume = cross_section_area * (main_length + screen_length)
    outer_length = data.storage_length_m + 2.0 * (data.wall_to_inner_toe_clearance_m + base_width)
    outer_width = data.storage_width_m + 2.0 * (data.wall_to_inner_toe_clearance_m + base_width)

    return BermDesignResult(
        berm_height_m=berm_height,
        crest_width_m=data.crest_width_m,
        base_width_m=base_width,
        cross_section_area_m2=cross_section_area,
        main_berm_centerline_length_m=main_length,
        screen_berm_length_m=screen_length,
        total_earthwork_volume_m3=total_volume,
        outer_footprint_length_m=outer_length,
        outer_footprint_width_m=outer_width,
        violations=violations,
    )
