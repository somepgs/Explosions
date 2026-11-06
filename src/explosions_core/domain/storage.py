"""Модели хранилищ, ПРП, передвижных складов и входа проекта."""

from pydantic import Field

from explosions_core.domain.base import InputModel
from explosions_core.domain.distances import ExternalProtectedObject
from explosions_core.domain.enums import (
    LocationType,
    StorageMethod,
    PackagingType,
    WarehouseCategory,
    WarehouseDuration,
)
from explosions_core.domain.explosives import ExplosiveItem


class InternalLayoutConfig(InputModel):
    storage_method: StorageMethod
    packaging: PackagingType
    unsealed_bc_or_black_powder: bool = False
    wall_clearance_m: float | None = Field(default=None, ge=0)
    floor_deck_height_m: float | None = Field(default=None, ge=0)
    aisle_width_stack_m: float | None = Field(default=None, ge=0)
    aisle_width_rack_m: float | None = Field(default=None, ge=0)
    stack_height_m: float | None = Field(default=None, ge=0)
    rack_shelf_height_m: float | None = Field(default=None, ge=0)
    tiers_per_shelf: int | None = Field(default=None, ge=0)


class BermParams(InputModel):
    height_m: float | None = Field(default=None, ge=0)
    top_width_m: float | None = Field(default=None, ge=0)


class StorageBuilding(InputModel):
    name: str
    storage_id: str | None = None
    category: WarehouseCategory
    duration: WarehouseDuration
    location_type: LocationType
    berm: BermParams | None = None
    is_bermed: bool = False
    items: list[ExplosiveItem] = Field(default_factory=list)
    layout: InternalLayoutConfig | None = None
    stack_width_b_m: float | None = Field(default=None, gt=0)
    x_m: float | None = None
    y_m: float | None = None
    length_m: float | None = Field(default=None, gt=0)
    width_m: float | None = Field(default=None, gt=0)


class UnloadingPlatformConfig(InputModel):
    fence_height_m: float | None = Field(default=None, ge=0)
    loading_point_to_fence_m: float | None = Field(default=None, ge=0)
    switch_distance_m: float | None = Field(default=None, ge=0)
    guardhouse_distance_m: float | None = Field(default=None, ge=0)


class MobileWarehouseConfig(InputModel):
    vehicle_name: str
    rated_payload_kg: float = Field(gt=0)
    payload_kg: float = Field(ge=0)
    is_specialized_vehicle: bool = False
    powder_separation_m: float | None = Field(default=None, ge=0)
    items: list[ExplosiveItem] = Field(default_factory=list)


class WarehouseProjectInput(InputModel):
    name: str
    storages: list[StorageBuilding] = Field(default_factory=list)
    forbidden_zone_width_m: float | None = Field(default=None, ge=0)
    fence_height_m: float | None = Field(default=None, ge=0)
    fence_to_nearest_storage_m: float | None = Field(default=None, ge=0)
    fence_to_guardhouse_m: float | None = Field(default=None, ge=0)
    fence_to_tare_storage_m: float | None = Field(default=None, ge=0)
    open_fire_ban_radius_m: float | None = Field(default=None, ge=0)
    unloading_platform: UnloadingPlatformConfig | None = None
    mobile_warehouse: MobileWarehouseConfig | None = None
    external_targets: list[ExternalProtectedObject] = Field(default_factory=list)
