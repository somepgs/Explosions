"""Расчет геометрии защитного обвалования хранилищ ВМ по п. 602–605 Приказа МИР РК № 343 (ред. от 02.10.2025).

п. 603 — грунт вала; п. 604 — гребень на 1,5 м выше верхнего уровня штабеля (стеллажа), ширина по верху не менее 1 м,
ширина по низу — по углу естественного откоса; п. 605 — защитный вал перед разрывом для выхода, длина по линии
визирования «угол здания — конечная точка гребня главного вала».

Геометрия плана: здание центрировано в начале координат, длина по оси X, проезд — в западной стене (−X).
Защитный вал примыкает внутренней подошвой к внешней подошве главного вала.
"""

import math

from explosions_core.domain import (
    BermDesignInput,
    BermDesignResult,
    BermSoilMaterial,
    NormativeViolation,
)
from explosions_core.norms.constants_rk343 import MIN_BERM_CREST_ELEVATION_ABOVE_LOAD_M, MIN_BERM_CREST_WIDTH_M
from explosions_core.norms.references import CLAUSE_BERM_CREST, CLAUSE_BERM_SCREEN, CLAUSE_BERM_SOIL

FORBIDDEN_BERM_SOIL = (BermSoilMaterial.STONE_OR_GRAVEL, BermSoilMaterial.COMBUSTIBLE_MATERIAL)


def screen_required_crest_length(data: BermDesignInput, base_width_m: float) -> float:
    """Минимальная длина гребня защитного вала по п. 605.

    Прямая от ближайшего угла здания (−L/2, W/2) через ближайшую конечную точку гребня главного вала у разрыва
    (внутренняя бровка гребня, y = ширина проезда / 2) должна пересечь гребень защитного вала. Требуемая полудлина
    гребня — наименьшее |y| прямой в пределах ширины гребня защитного вала.
    """
    run = (base_width_m - data.crest_width_m) / 2.0
    corner_x, corner_y = -data.storage_length_m / 2.0, data.storage_width_m / 2.0
    end_x = corner_x - data.wall_to_inner_toe_clearance_m - run
    end_y = data.entrance_opening_width_m / 2.0
    slope = (end_y - corner_y) / (end_x - corner_x)

    main_outer_toe_x = corner_x - data.wall_to_inner_toe_clearance_m - base_width_m
    screen_crest_near_x = main_outer_toe_x - run
    screen_crest_far_x = screen_crest_near_x - data.crest_width_m

    def y_at(x: float) -> float:
        return corner_y + slope * (x - corner_x)

    y_near, y_far = y_at(screen_crest_near_x), y_at(screen_crest_far_x)
    half_length = 0.0 if y_near * y_far <= 0.0 else min(abs(y_near), abs(y_far))
    return 2.0 * half_length


def calculate_berm_design(data: BermDesignInput) -> BermDesignResult:
    violations: list[NormativeViolation] = []

    if data.soil_material in FORBIDDEN_BERM_SOIL:
        violations.append(
            NormativeViolation(
                code="BERM_INVALID_SOIL_MATERIAL",
                clause=CLAUSE_BERM_SOIL,
                description="Для насыпки валов не допускается использовать камень, щебень и горючие материалы",
                actual_value=data.soil_material.value,
                required_value="plastic_clay_loam или sandy_free_flowing",
            )
        )
    if data.crest_width_m < MIN_BERM_CREST_WIDTH_M:
        violations.append(
            NormativeViolation(
                code="BERM_CREST_WIDTH_TOO_SMALL",
                clause=CLAUSE_BERM_CREST,
                description="Ширина вала по верху меньше 1 м",
                actual_value=data.crest_width_m,
                required_value=MIN_BERM_CREST_WIDTH_M,
            )
        )
    if data.crest_elevation_above_load_m < MIN_BERM_CREST_ELEVATION_ABOVE_LOAD_M:
        violations.append(
            NormativeViolation(
                code="BERM_CREST_TOO_LOW",
                clause=CLAUSE_BERM_CREST,
                description="Гребень вала ниже чем на 1,5 м над верхним уровнем штабеля (стеллажа) с ВМ",
                actual_value=data.crest_elevation_above_load_m,
                required_value=MIN_BERM_CREST_ELEVATION_ABOVE_LOAD_M,
            )
        )

    berm_height = data.load_top_height_m + data.crest_elevation_above_load_m
    if berm_height <= 0.0:
        raise ValueError(
            f"Высота вала H_в = {berm_height:.2f} м должна быть больше нуля; проверьте высоту груза и превышение гребня"
        )
    tan_slope = math.tan(math.radians(data.natural_slope_angle_deg))
    base_width = data.crest_width_m + 2.0 * berm_height / tan_slope
    cross_section_area = 0.5 * (data.crest_width_m + base_width) * berm_height

    offset_to_centerline = data.wall_to_inner_toe_clearance_m + base_width / 2.0
    perimeter_centerline = 2.0 * (data.storage_length_m + data.storage_width_m) + 8.0 * offset_to_centerline
    opening = data.entrance_opening_width_m if data.has_entrance_screen_berm else 0.0
    main_length = max(0.0, perimeter_centerline - opening)

    screen_required: float | None = None
    if data.has_entrance_screen_berm:
        screen_length = data.entrance_opening_width_m + 2.0 * data.screen_overlap_each_side_m
        screen_required = screen_required_crest_length(data, base_width)
        if screen_length < screen_required:
            violations.append(
                NormativeViolation(
                    code="BERM_SCREEN_TOO_SHORT",
                    clause=CLAUSE_BERM_SCREEN,
                    description=(
                        "Защитный вал короче требуемого: прямая от угла здания через конечную точку гребня главного "
                        "вала не проходит через гребень защитного вала"
                    ),
                    actual_value=screen_length,
                    required_value=screen_required,
                )
            )
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
        screen_required_length_m=screen_required,
        total_earthwork_volume_m3=total_volume,
        outer_footprint_length_m=outer_length,
        outer_footprint_width_m=outer_width,
        violations=violations,
    )
