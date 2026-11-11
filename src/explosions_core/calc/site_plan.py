"""Расстояния генплана склада для чертежей и предпросмотра.

Берутся проектные значения из `WarehouseProjectInput`; если значение не задано — нормативный минимум
по типу склада (постоянный, временный — п. 590, 592, 593, 618; кратковременный — п. 621). Соответствие
проектных значений нормам проверяет `validate_perimeter`; здесь значения только выбираются для построения.
"""

from dataclasses import dataclass

from explosions_core.domain import WarehouseDuration, WarehouseProjectInput
from explosions_core.norms.constants_rk343 import (
    MIN_DIST_FENCE_TO_GUARDHOUSE_M,
    MIN_DIST_FENCE_TO_GUARDHOUSE_SHORT_TERM_M,
    MIN_DIST_FENCE_TO_STORAGE_M,
    MIN_DIST_FENCE_TO_STORAGE_SHORT_TERM_M,
    MIN_DIST_FENCE_TO_TARE_STORAGE_M,
    MIN_FORBIDDEN_ZONE_WIDTH_M,
    MIN_OPEN_FIRE_BAN_RADIUS_M,
)
from explosions_core.validators.layout_and_perimeter import governing_warehouse_duration


@dataclass(frozen=True)
class SitePlanDistances:
    """Расстояния для построения генплана, м.

    `forbidden_zone_width_m` и `fence_to_tare_storage_m` равны None, если для кратковременного склада
    они не заданы проектом: запретная зона п. 590 и навес для тары п. 592 к нему не применяются
    (docs/assumptions.md, п. 11).
    """

    duration: WarehouseDuration
    fence_to_storage_m: float
    forbidden_zone_width_m: float | None
    open_fire_ban_radius_m: float
    fence_to_guardhouse_m: float
    fence_to_tare_storage_m: float | None


def site_plan_distances(project: WarehouseProjectInput) -> SitePlanDistances:
    duration = governing_warehouse_duration(project)
    short_term = duration == WarehouseDuration.SHORT_TERM

    zone = project.forbidden_zone_width_m
    if zone is None and not short_term:
        zone = MIN_FORBIDDEN_ZONE_WIDTH_M

    if project.fence_to_guardhouse_m is not None:
        guardhouse = project.fence_to_guardhouse_m
    elif short_term:
        guardhouse = MIN_DIST_FENCE_TO_GUARDHOUSE_SHORT_TERM_M
    else:
        guardhouse = max(MIN_DIST_FENCE_TO_GUARDHOUSE_M, zone or 0.0)

    tare = project.fence_to_tare_storage_m
    if tare is None and not short_term:
        tare = MIN_DIST_FENCE_TO_TARE_STORAGE_M

    return SitePlanDistances(
        duration=duration,
        fence_to_storage_m=_value_or(
            project.fence_to_nearest_storage_m,
            MIN_DIST_FENCE_TO_STORAGE_SHORT_TERM_M if short_term else MIN_DIST_FENCE_TO_STORAGE_M,
        ),
        forbidden_zone_width_m=zone,
        open_fire_ban_radius_m=_value_or(project.open_fire_ban_radius_m, MIN_OPEN_FIRE_BAN_RADIUS_M),
        fence_to_guardhouse_m=guardhouse,
        fence_to_tare_storage_m=tare,
    )


def _value_or(value: float | None, default: float) -> float:
    return value if value is not None else default
