"""Расчет молниезащиты хранилищ ВМ.

Основной метод: катящаяся сфера по формуле (2-1) СП РК 2.04-103-2013 (п. 7.2) с радиусом D по уровню защиты.
Метод СО 153-34.21.122-2003: зона одиночного стержневого молниеотвода по табл. 3.4 и формуле (3.1)
для надежности 0,9 / 0,99 / 0,999.
Устаревший метод: зоны А и Б по РД 34.21.122-87 (текст РД в Documentation отсутствует).
"""

import math

from explosions_core.domain import (
    CheckPoint3D,
    LightningArresterMast,
    LightningMethod,
    LightningProtectionLevel,
    LightningProtectionResult,
    LightningReliability,
    LightningZoneType,
    LocationType,
    NormativeViolation,
    StorageBuilding,
    WarehouseDuration,
)
from explosions_core.norms.constants_rk343 import (
    ARRESTER_HEIGHT_SEARCH_STEP_M,
    DEFAULT_VENT_ABOVE_RIDGE_M,
    MAX_ROD_ARRESTER_HEIGHT_M,
    DEFAULT_SO153_RELIABILITY,
    MIN_ARRESTER_CLEARANCE_FROM_STORAGE_WALL_M,
    ROLLING_SPHERE_RADIUS_BY_LEVEL_M,
    ZONE_A_H0_COEFF,
    ZONE_A_R0_BASE,
    ZONE_A_R0_SLOPE,
    ZONE_B_H0_COEFF,
    ZONE_B_R0_COEFF,
)
from explosions_core.norms.references import CLAUSE_ARRESTER_CLEARANCE, CLAUSE_LIGHTNING_REQUIRED

LIGHTNING_REQUIRED_DURATIONS = (WarehouseDuration.PERMANENT, WarehouseDuration.TEMPORARY)


def lightning_protection_required(storage: StorageBuilding) -> bool:
    """П. 691: защита от ПУМ обязательна для постоянных и временных складов; п. 693: кратковременные — можно не оборудовать.

    Подземные хранилища не проверяются (п. 686, покрытие более 10 м — допущение, см. docs/assumptions.md).
    """
    return storage.duration in LIGHTNING_REQUIRED_DURATIONS and storage.location_type != LocationType.UNDERGROUND


def lightning_required_violation(storage: StorageBuilding, storage_id: str, *, has_protection: bool) -> NormativeViolation | None:
    if has_protection or not lightning_protection_required(storage):
        return None
    return NormativeViolation(
        code="LIGHTNING_REQUIRED",
        clause=CLAUSE_LIGHTNING_REQUIRED,
        description=(
            f"Хранилище '{storage_id}': не задан раздел молниезащиты, а она обязательна "
            "для постоянного и временного склада"
        ),
        actual_value="не задана",
        required_value="защита от ПУМ и вторичных воздействий",
    )


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


def so153_cone_parameters(height_m: float, reliability: LightningReliability | str) -> tuple[float, float]:
    """Высота конуса h0 и радиус на уровне земли r0 по табл. 3.4 СО 153-34.21.122-2003 (h ≤ 150 м)."""
    if not 0.0 < height_m <= MAX_ROD_ARRESTER_HEIGHT_M:
        raise ValueError(f"Высота молниеотвода должна быть в диапазоне (0; {MAX_ROD_ARRESTER_HEIGHT_M}] м")
    h = height_m
    level = LightningReliability(reliability)
    if level == LightningReliability.P_0_9:
        h0 = 0.85 * h
        r0 = 1.2 * h if h <= 100.0 else (1.2 - 1e-3 * (h - 100.0)) * h
    elif level == LightningReliability.P_0_99:
        if h <= 30.0:
            h0, r0 = 0.8 * h, 0.8 * h
        elif h <= 100.0:
            h0, r0 = 0.8 * h, (0.8 - 1.43e-3 * (h - 30.0)) * h
        else:
            h0, r0 = (0.8 - 1e-3 * (h - 100.0)) * h, 0.7 * h
    else:
        if h <= 30.0:
            h0, r0 = 0.7 * h, 0.6 * h
        elif h <= 100.0:
            h0, r0 = (0.7 - 7.14e-4 * (h - 30.0)) * h, (0.6 - 1.43e-3 * (h - 30.0)) * h
        else:
            h0, r0 = (0.65 - 1e-3 * (h - 100.0)) * h, (0.5 - 2e-3 * (h - 100.0)) * h
    return h0, r0


def so153_single_rod_zone(
    height_m: float, hx_m: float, reliability: LightningReliability | str
) -> tuple[float, float, float]:
    """(h0, r0, rx) по табл. 3.4 и формуле (3.1) СО 153: rx = r0·(h0 − hx)/h0; rx = 0 при hx ≥ h0."""
    h0, r0 = so153_cone_parameters(height_m, reliability)
    rx = 0.0 if hx_m >= h0 else r0 * (h0 - hx_m) / h0
    return h0, r0, rx


def rolling_sphere_radius(height_m: float, hx_m: float, sphere_radius_m: float) -> float:
    """Радиус защиты на высоте hx по формуле (2-1) СП РК 2.04-103-2013: Rp = sqrt(h'(2D - h')), h' = h - hx.

    Защита на отметке отсутствует, если h' <= 0 или h' >= 2D (формула (2-1а) действует при h' < 2D).
    """
    if height_m <= 0.0 or sphere_radius_m <= 0.0:
        raise ValueError("Высота молниеотвода и радиус сферы должны быть положительными")
    effective = height_m - hx_m
    if effective <= 0.0 or effective >= 2.0 * sphere_radius_m:
        return 0.0
    return math.sqrt(effective * (2.0 * sphere_radius_m - effective))


def sphere_radius_for_level(protection_level: LightningProtectionLevel | str) -> float:
    key = LightningProtectionLevel(protection_level).value
    return ROLLING_SPHERE_RADIUS_BY_LEVEL_M[key]


def resolve_lightning_method(method: LightningMethod | None, zone_type: LightningZoneType | None) -> LightningMethod:
    """Метод не задан: при указанном типе зоны — зоны РД 34.21.122-87 (совместимость), иначе катящаяся сфера СП РК."""
    if method is not None:
        return LightningMethod(method)
    return LightningMethod.ZONES_RD_34_21_122 if zone_type is not None else LightningMethod.ROLLING_SPHERE_SP_RK


def _check_method_arguments(method: LightningMethod, zone_type: LightningZoneType | None) -> None:
    if method != LightningMethod.ZONES_RD_34_21_122 and zone_type is not None:
        raise ValueError(
            "Тип зоны (zone_type) задается только для метода зон РД 34.21.122-87 (method=zones_rd_34_21_122)"
        )
    if method == LightningMethod.ZONES_RD_34_21_122 and zone_type is None:
        raise ValueError("Для метода зон РД 34.21.122-87 обязателен тип зоны (zone_type)")


def protection_radius(
    height_m: float,
    hx_m: float,
    *,
    method: LightningMethod | None = None,
    zone_type: LightningZoneType | None = None,
    protection_level: LightningProtectionLevel | str = LightningProtectionLevel.LEVEL_I,
    reliability: LightningReliability | str = DEFAULT_SO153_RELIABILITY,
) -> float:
    method = resolve_lightning_method(method, zone_type)
    if method == LightningMethod.ROLLING_SPHERE_SP_RK:
        return rolling_sphere_radius(height_m, hx_m, sphere_radius_for_level(protection_level))
    if method == LightningMethod.SINGLE_ROD_SO_153:
        return so153_single_rod_zone(height_m, hx_m, reliability)[2]
    _check_method_arguments(method, zone_type)
    _, _, rx = single_rod_zone(height_m, hx_m, zone_type)
    return rx


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


def _point_covered(
    x_m: float,
    y_m: float,
    height_m: float,
    point: CheckPoint3D,
    *,
    method: LightningMethod | None,
    zone_type: LightningZoneType | None,
    protection_level: LightningProtectionLevel | str,
    reliability: LightningReliability | str = DEFAULT_SO153_RELIABILITY,
) -> bool:
    rx = protection_radius(
        height_m,
        point.z_height_m,
        method=method,
        zone_type=zone_type,
        protection_level=protection_level,
        reliability=reliability,
    )
    return rx > 0.0 and math.hypot(point.x_m - x_m, point.y_m - y_m) <= rx


def all_points_covered(
    positions: list[tuple[float, float]],
    height_m: float,
    checkpoints: list[CheckPoint3D],
    zone_type: LightningZoneType | None = None,
    *,
    method: LightningMethod | None = None,
    protection_level: LightningProtectionLevel | str = LightningProtectionLevel.LEVEL_I,
    reliability: LightningReliability | str = DEFAULT_SO153_RELIABILITY,
) -> bool:
    return all(
        any(
            _point_covered(
                x_m,
                y_m,
                height_m,
                point,
                method=method,
                zone_type=zone_type,
                protection_level=protection_level,
                reliability=reliability,
            )
            for x_m, y_m in positions
        )
        for point in checkpoints
    )


def solve_common_arrester_height(
    positions: list[tuple[float, float]],
    checkpoints: list[CheckPoint3D],
    zone_type: LightningZoneType | None = None,
    *,
    method: LightningMethod | None = None,
    protection_level: LightningProtectionLevel | str = LightningProtectionLevel.LEVEL_I,
    reliability: LightningReliability | str = DEFAULT_SO153_RELIABILITY,
) -> float | None:
    """Минимальная общая высота мачт, при которой каждая контрольная точка защищена хотя бы одной мачтой.

    Для катящейся сферы защита немонотонна по высоте (радиус падает при h' > D), поэтому выполняется перебор
    с шагом ARRESTER_HEIGHT_SEARCH_STEP_M и берется первая высота, дающая полное покрытие. Так же
    считается метод СО 153 (формулы табл. 3.4 кусочные). Для зон РД покрытие монотонно по высоте,
    поэтому используется бисекция.
    """
    if not positions:
        raise ValueError("Не заданы мачты молниеотводов")
    if not checkpoints:
        raise ValueError("Не заданы контрольные точки здания")
    method = resolve_lightning_method(method, zone_type)
    _check_method_arguments(method, zone_type)
    max_z = max(point.z_height_m for point in checkpoints)
    coverage_kwargs = {
        "method": method,
        "zone_type": zone_type,
        "protection_level": protection_level,
        "reliability": reliability,
    }

    if method != LightningMethod.ZONES_RD_34_21_122:
        steps_total = round(MAX_ROD_ARRESTER_HEIGHT_M / ARRESTER_HEIGHT_SEARCH_STEP_M)
        for index in range(1, steps_total + 1):
            height = round(index * ARRESTER_HEIGHT_SEARCH_STEP_M, 1)
            if height <= max_z:
                continue
            if all_points_covered(positions, height, checkpoints, **coverage_kwargs):
                return height
        return None

    k0 = ZONE_A_H0_COEFF if zone_type == LightningZoneType.ZONE_A else ZONE_B_H0_COEFF
    lower = max_z / k0
    upper = MAX_ROD_ARRESTER_HEIGHT_M
    if not all_points_covered(positions, upper, checkpoints, **coverage_kwargs):
        return None
    while upper - lower > ARRESTER_HEIGHT_SEARCH_STEP_M:
        middle = (lower + upper) / 2.0
        if all_points_covered(positions, middle, checkpoints, **coverage_kwargs):
            upper = middle
        else:
            lower = middle
    steps = math.ceil(round(upper / ARRESTER_HEIGHT_SEARCH_STEP_M, 9))
    return round(steps * ARRESTER_HEIGHT_SEARCH_STEP_M, 1)


def solve_minimum_arrester_height(
    x_m: float,
    y_m: float,
    checkpoints: list[CheckPoint3D],
    zone_type: LightningZoneType | None = None,
    *,
    method: LightningMethod | None = None,
    protection_level: LightningProtectionLevel | str = LightningProtectionLevel.LEVEL_I,
    reliability: LightningReliability | str = DEFAULT_SO153_RELIABILITY,
) -> float | None:
    return solve_common_arrester_height(
        [(x_m, y_m)],
        checkpoints,
        method=method,
        zone_type=zone_type,
        protection_level=protection_level,
        reliability=reliability,
    )


def calculate_lightning_protection(
    masts: list[LightningArresterMast],
    zone_type: LightningZoneType | None,
    storage_length_m: float,
    storage_width_m: float,
    eaves_height_m: float,
    ridge_height_m: float,
    checkpoints: list[CheckPoint3D] | None = None,
    vent_height_m: float | None = None,
    *,
    method: LightningMethod | None = None,
    protection_level: LightningProtectionLevel | str = LightningProtectionLevel.LEVEL_I,
    reliability: LightningReliability | str = DEFAULT_SO153_RELIABILITY,
) -> LightningProtectionResult:
    method = resolve_lightning_method(method, zone_type)
    _check_method_arguments(method, zone_type)
    coverage_kwargs = {
        "method": method,
        "zone_type": zone_type,
        "protection_level": protection_level,
        "reliability": reliability,
    }
    if checkpoints is None:
        checkpoints = generate_storage_checkpoints_3d(
            storage_length_m, storage_width_m, eaves_height_m, ridge_height_m, vent_height_m
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
        h0_m = None
        if method == LightningMethod.SINGLE_ROD_SO_153:
            h0_m, _ = so153_cone_parameters(mast.height_h_m, reliability)
        elif zone_type is not None:
            h0_m, _, _ = single_rod_zone(mast.height_h_m, 0.0, zone_type)
        r0 = protection_radius(mast.height_h_m, 0.0, **coverage_kwargs)
        rx_eaves = protection_radius(mast.height_h_m, eaves_height_m, **coverage_kwargs)
        rx_ridge = protection_radius(mast.height_h_m, ridge_height_m, **coverage_kwargs)
        mast_results.append(
            {
                "mast_id": mast.mast_id,
                "h0_m": h0_m,
                "r0_ground_m": r0,
                "rx_at_eaves_m": rx_eaves,
                "rx_at_ridge_m": rx_ridge,
            }
        )

    solved_height = (
        solve_common_arrester_height([(mast.x_m, mast.y_m) for mast in masts], checkpoints, **coverage_kwargs)
        if masts
        else None
    )

    unprotected = [
        point.name
        for point in checkpoints
        if not any(
            _point_covered(mast.x_m, mast.y_m, mast.height_h_m, point, **coverage_kwargs) for mast in masts
        )
    ]

    return LightningProtectionResult(
        method=method,
        protection_level=protection_level,
        reliability=reliability,
        zone_type=zone_type,
        mast_results=mast_results,
        min_recommended_mast_height_m=solved_height,
        unprotected_points=unprotected,
        is_fully_protected=not unprotected and not violations and bool(masts),
        violations=violations,
    )
