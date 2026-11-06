"""Модели расчета стеллажей, штабелей и габаритов хранилища (п. 579–580)."""

from pydantic import BaseModel, ConfigDict, Field

from explosions_core.domain.enums import CompatibilityGroup, PackagingType, StorageMethod
from explosions_core.domain.explosives import UnitPackageSpec
from explosions_core.domain.results import NormativeViolation
from explosions_core.norms.constants_rk343 import (
    DEFAULT_SHELF_THICKNESS_M,
    MIN_FLOOR_DECK_HEIGHT_M,
    MIN_SHELF_VERTICAL_GAP_M,
    MIN_WALL_CLEARANCE_M,
)


class StorageSizingInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_net_explosive_mass_kg: float = Field(gt=0)
    compatibility_group: CompatibilityGroup
    is_black_powder: bool = False
    is_unsealed: bool = False
    storage_method: StorageMethod
    packaging_type: PackagingType
    is_mechanized: bool = False
    unit_spec: UnitPackageSpec
    wall_racks_count: int = Field(default=2, ge=0, le=2, alias="wall_Reifen_rows_count")
    island_rows_count: int = Field(default=2, ge=1)
    cross_aisles_count: int = Field(default=2, ge=0)
    shelf_thickness_m: float = Field(default=DEFAULT_SHELF_THICKNESS_M, ge=0)
    floor_deck_height_m: float = Field(default=MIN_FLOOR_DECK_HEIGHT_M, ge=0)
    wall_clearance_m: float = Field(default=MIN_WALL_CLEARANCE_M, ge=0)
    shelf_vertical_gap_m: float = Field(default=MIN_SHELF_VERTICAL_GAP_M, ge=0)
    preferred_units_along_single_line: int | None = Field(default=None, ge=1)


class StorageSizingResult(BaseModel):
    total_units_required: int
    total_gross_weight_kg: float
    shelves_or_tiers_count: int
    tiers_per_shelf: int
    shelf_step_height_m: float | None = None
    top_shelf_height_m: float | None = None
    total_loaded_height_m: float
    required_aisle_width_m: float
    line_length_m: float
    min_internal_width_m: float
    min_internal_length_m: float
    min_internal_height_m: float
    useful_storage_area_m2: float
    total_internal_area_m2: float
    area_utilization_coeff: float
    units_per_cross_section: int
    units_along_line: int
    wall_rack_depth_m: float
    island_line_depth_m: float
    violations: list[NormativeViolation] = Field(default_factory=list)
