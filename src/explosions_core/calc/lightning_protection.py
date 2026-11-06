"""Расчет зон молниезащиты хранилищ ВМ по п. 8.1.1 СП РК 2.04-103-2013 (одиночный стержневой молниеотвод)."""

import math

from explosions_core.domain import (
    CheckPoint3D,
    LightningArresterMast,
    LightningProtectionResult,
    LightningZoneType,
    NormativeViolation,
)
from explosions_core.norms.constants_rk343 import (
    ARRESTER_HEIGHT_SEARCH_STEP_M,
    DEFAULT_VENT_ABOVE_RIDGE_M,
    MAX_ROD_ARRESTER_HEIGHT_M,
    MIN_ARRESTER_CLEARANCE_FROM_STORAGE_WALL_M,
    ZONE_A_H0_COEFF,
    ZONE_A_R0_BASE,
    ZONE_A_R0_SLOPE,
    ZONE_B_H0_COEFF,
    ZONE_B_R0_COEFF,
)
from explosions_core.norms.references import CLAUSE_ARRESTER_CLEARANCE


def single_rod_zone(height_m: float, hx_m: float, zone_type: LightningZoneType) -> tuple[float, float, float]:
    if not 0.0 < height_m <= MAX_ROD_ARRESTER_HEIGHT_M:
        raise ValueError(f"Высота молниеотвода должна быть в диапазоне (0; {MAX_ROD_ARRESTER_HEIGHT_M}] м")
    if zone_type == LightningZoneType.ZONE_A:
        h0 = ZONE_A_H0_COEFF * height_m
        k = ZONE_A_R0_BASE - ZONE_A_R0_SLOPE * height_m
        r0 = k * height_m
        rx = 0.0 if hx_m >= h0 else k * (height_m - hx_m / ZONE_A_H0_COEFF)
    else:
        h0 = ZONE_B_H0_COEFF * height_m
        r0 = ZONE_B_R0_COEFF * height_m
        rx = 0.0 if hx_m >= h0 else ZONE_B_R0_COEFF * (height_m - hx_m / ZONE_B_H0_COEFF)
    return h0, r0, rx


def generate_storage_checkpoints_3d(
    length_m: float,
    width_m: float,
    eaves_height_m: float,
    ridge_height_m: float,
    vent_height_m: float | None = None,
) -> list[CheckPoint3D]:
    if ridge_height_m < eaves_height_m:
        raise ValueError("Высота конька не может быть меньше высоты карниза")
    if vent_height_m is None:
        vent_height_m = ridge_height_m + DEFAULT_VENT_ABOVE_RIDGE_M
    half_length = length_m / 2.0
    half_width = width_m / 2.0
    return [
        CheckPoint3D(name="Северо-восточный угол карниза", x_m=half_length, y_m=half_width, z_height_m=eaves_height_m),
        CheckPoint3D(name="Северо-западный угол карниза", x_m=-half_length, y_m=half_width, z_height_m=eaves_height_m),
        CheckPoint3D(name="Юго-восточный угол карниза", x_m=half_length, y_m=-half_width, z_height_m=eaves_height_m),
        CheckPoint3D(name="Юго-западный угол карниза", x_m=-half_length, y_m=-half_width, z_height_m=eaves_height_m),
        CheckPoint3D(name="Торец конька (восток)", x_m=half_length, y_m=0.0, z_height_m=ridge_height_m),
        CheckPoint3D(name="Торец конька (запад)", x_m=-half_length, y_m=0.0, z_height_m=ridge_height_m),
        CheckPoint3D(name="Верх дефлектора вентшахты", x_m=0.0, y_m=0.0, z_height_m=vent_height_m),
    ]


def distance_to_building(x_m: float, y_m: float, length_m: float, width_m: float) -> float:
    dx = max(abs(x_m) - length_m / 2.0, 0.0)
    dy = max(abs(y_m) - width_m / 2.0, 0.0)
    return math.hypot(dx, dy)


def _point_covered(x_m: float, y_m: float, height_m: float, point: CheckPoint3D, zone_type: LightningZoneType) -> bool:
    _, _, rx = single_rod_zone(height_m, point.z_height_m, zone_type)
    return rx > 0.0 and math.hypot(point.x_m - x_m, point.y_m - y_m) <= rx


def all_points_covered(
    positions: list[tuple[float, float]],
    height_m: float,
    checkpoints: list[CheckPoint3D],
    zone_type: LightningZoneType,
) -> bool:
    return all(
        any(_point_covered(x_m, y_m, height_m, point, zone_type) for x_m, y_m in positions)
        for point in checkpoints
    )


def solve_common_arrester_height(
    positions: list[tuple[float, float]],
    checkpoints: list[CheckPoint3D],
    zone_type: LightningZoneType,
) -> float | None:
    if not positions:
        raise ValueError("Не заданы мачты молниеотводов")
    if not checkpoints:
        raise ValueError("Не заданы контрольные точки здания")
    k0 = ZONE_A_H0_COEFF if zone_type == LightningZoneType.ZONE_A else ZONE_B_H0_COEFF
    lower = max(point.z_height_m for point in checkpoints) / k0
    upper = MAX_ROD_ARRESTER_HEIGHT_M
    if not all_points_covered(positions, upper, checkpoints, zone_type):
        return None
    while upper - lower > ARRESTER_HEIGHT_SEARCH_STEP_M:
        middle = (lower + upper) / 2.0
        if all_points_covered(positions, middle, checkpoints, zone_type):
            upper = middle
        else:
            lower = middle
    steps = math.ceil(round(upper / ARRESTER_HEIGHT_SEARCH_STEP_M, 9))
    return round(steps * ARRESTER_HEIGHT_SEARCH_STEP_M, 1)


def solve_minimum_arrester_height(
    x_m: float,
    y_m: float,
    checkpoints: list[CheckPoint3D],
    zone_type: LightningZoneType,
) -> float | None:
    return solve_common_arrester_height([(x_m, y_m)], checkpoints, zone_type)


def calculate_lightning_protection(
    masts: list[LightningArresterMast],
    zone_type: LightningZoneType,
    storage_length_m: float,
    storage_width_m: float,
    eaves_height_m: float,
    ridge_height_m: float,
    checkpoints: list[CheckPoint3D] | None = None,
) -> LightningProtectionResult:
    if checkpoints is None:
        checkpoints = generate_storage_checkpoints_3d(
            storage_length_m, storage_width_m, eaves_height_m, ridge_height_m
        )

    violations: list[NormativeViolation] = []
    mast_results: list[dict] = []
    for mast in masts:
        distance = distance_to_building(mast.x_m, mast.y_m, storage_length_m, storage_width_m)
        if distance < MIN_ARRESTER_CLEARANCE_FROM_STORAGE_WALL_M:
            violations.append(
                NormativeViolation(
                    code="LIGHTNING_MAST_TOO_CLOSE_TO_STORAGE",
                    clause=CLAUSE_ARRESTER_CLEARANCE,
                    description=f"Мачта '{mast.mast_id}' расположена ближе минимума до стен хранилища",
                    actual_value=distance,
                    required_value=MIN_ARRESTER_CLEARANCE_FROM_STORAGE_WALL_M,
                )
            )
        h0, r0, _ = single_rod_zone(mast.height_h_m, 0.0, zone_type)
        _, _, rx_eaves = single_rod_zone(mast.height_h_m, eaves_height_m, zone_type)
        _, _, rx_ridge = single_rod_zone(mast.height_h_m, ridge_height_m, zone_type)
        mast_results.append(
            {
                "mast_id": mast.mast_id,
                "h0_m": h0,
                "r0_ground_m": r0,
                "rx_at_eaves_m": rx_eaves,
                "rx_at_ridge_m": rx_ridge,
            }
        )

    solved_height = (
        solve_common_arrester_height([(mast.x_m, mast.y_m) for mast in masts], checkpoints, zone_type)
        if masts
        else None
    )

    unprotected = [
        point.name
        for point in checkpoints
        if not any(_point_covered(mast.x_m, mast.y_m, mast.height_h_m, point, zone_type) for mast in masts)
    ]

    return LightningProtectionResult(
        zone_type=zone_type,
        mast_results=mast_results,
        min_recommended_mast_height_m=solved_height,
        unprotected_points=unprotected,
        is_fully_protected=not unprotected and not violations and bool(masts),
        violations=violations,
    )
