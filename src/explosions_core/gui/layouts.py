"""Раскладка полей форм по шагам мастера: основные поля на виду, редкие — в «Дополнительно» (без Qt).

Поля вне раскладки шага не удаляются и не сбрасываются: форма сохраняет их значения при сборе данных.
Списки имен проверяются тестом против реальных моделей, поэтому опечатка здесь падает сразу.
"""

from dataclasses import dataclass

from explosions_core.domain import (
    BermSpec,
    CalculationSettings,
    ExplosiveItem,
    ExternalProtectedObject,
    InternalLayoutConfig,
    LightningArresterMast,
    LightningSpec,
    MobileWarehouseConfig,
    StorageBuilding,
    StorageDesignInput,
    StorageSizingInput,
    UnitPackageSpec,
    UnloadingPlatformConfig,
    WarehouseProjectInput,
)


@dataclass(frozen=True)
class FormLayout:
    """Поля, показанные сразу, и поля блока «Дополнительно»."""

    basic: tuple[str, ...]
    advanced: tuple[str, ...] = ()

    def all_fields(self) -> tuple[str, ...]:
        return self.basic + self.advanced


PROJECT_LAYOUT = FormLayout(basic=("name",), advanced=())

TERRITORY_LAYOUT = FormLayout(
    basic=(
        "fence_height_m",
        "fence_to_nearest_storage_m",
        "forbidden_zone_width_m",
        "open_fire_ban_radius_m",
        "unloading_platform",
        "mobile_warehouse",
    ),
    advanced=("fence_to_guardhouse_m", "fence_to_tare_storage_m"),
)

STORAGE_GENERAL_LAYOUT = FormLayout(
    basic=("name", "storage_id", "location_type", "is_bermed", "items"),
    advanced=("category", "duration", "stack_width_b_m"),
)

BUILDING_PLACEMENT_LAYOUT = FormLayout(
    basic=("x_m", "y_m"),
    advanced=("length_m", "width_m"),
)

EXPLOSIVE_LAYOUT = FormLayout(
    basic=("name", "mass_kg", "group", "hazard_subclass", "detonation_class"),
    advanced=(
        "tnt_equivalent_coeff",
        "si_count",
        "is_initiating_device",
        "is_black_powder",
        "is_smokeless_powder",
        "is_detonating_cord",
    ),
)

# Шаг 3: фактическая планировка существующего хранилища (проверка п. 579–580 без расчета габаритов)
ACTUAL_LAYOUT_STEP_LAYOUT = FormLayout(basic=("layout",), advanced=())

INTERNAL_LAYOUT = FormLayout(
    basic=(
        "storage_method",
        "packaging",
        "unsealed_bc_or_black_powder",
        "wall_clearance_m",
        "floor_deck_height_m",
        "aisle_width_stack_m",
        "aisle_width_rack_m",
        "stack_height_m",
        "rack_shelf_height_m",
        "tiers_per_shelf",
    ),
    advanced=(),
)

SIZING_LAYOUT = FormLayout(
    basic=(
        "total_net_explosive_mass_kg",
        "compatibility_group",
        "storage_method",
        "packaging_type",
        "unit_spec",
    ),
    advanced=(
        "is_black_powder",
        "is_unsealed",
        "is_mechanized",
        "wall_racks_count",
        "island_rows_count",
        "cross_aisles_count",
        "shelf_thickness_m",
        "floor_deck_height_m",
        "wall_clearance_m",
        "shelf_vertical_gap_m",
        "preferred_units_along_single_line",
    ),
)

UNIT_PACKAGE_LAYOUT = FormLayout(
    basic=("net_weight_kg", "gross_weight_kg", "length_m", "width_m", "height_m"),
    advanced=("unit_gap_m",),
)

PLACEMENT_LAYOUT = FormLayout(
    basic=("eaves_height_m", "berm"),
    advanced=("load_top_height_m",),
)

SIZING_STEP_LAYOUT = FormLayout(basic=("sizing",), advanced=())

LIGHTNING_STEP_LAYOUT = FormLayout(basic=("eaves_height_m", "ridge_height_m", "lightning"), advanced=())

UNLOADING_PLATFORM_LAYOUT = FormLayout(
    basic=("fence_height_m", "loading_point_to_fence_m", "switch_distance_m", "guardhouse_distance_m"),
    advanced=(),
)

MOBILE_WAREHOUSE_LAYOUT = FormLayout(
    basic=("vehicle_name", "rated_payload_kg", "payload_kg", "items"),
    advanced=("is_specialized_vehicle", "powder_separation_m"),
)

BERM_LAYOUT = FormLayout(
    basic=("crest_elevation_above_load_m", "crest_width_m", "soil_material", "natural_slope_angle_deg"),
    advanced=("wall_to_inner_toe_clearance_m", "has_entrance_screen_berm", "entrance_opening_width_m", "screen_overlap_each_side_m"),
)

LIGHTNING_LAYOUT = FormLayout(
    basic=("method", "masts", "vent_height_m"),
    advanced=("protection_level", "reliability", "zone_type"),
)

MAST_LAYOUT = FormLayout(basic=("mast_id", "x_m", "y_m", "height_h_m"), advanced=())

TARGET_LAYOUT = FormLayout(
    basic=("object_id", "name", "actual_distance_m", "allowed_damage_degree"),
    advanced=("table3_object_category", "custom_kv_override", "topography_reduction_coeff", "bearing_deg"),
)

SETTINGS_LAYOUT = FormLayout(
    basic=(),
    advanced=("detonation_formula", "uvv_placement", "uvv_method", "wall_thickness_m"),
)

ALL_LAYOUTS: dict[str, FormLayout] = {
    "project": PROJECT_LAYOUT,
    "territory": TERRITORY_LAYOUT,
    "storage_general": STORAGE_GENERAL_LAYOUT,
    "building_placement": BUILDING_PLACEMENT_LAYOUT,
    "sizing_step": SIZING_STEP_LAYOUT,
    "lightning_step": LIGHTNING_STEP_LAYOUT,
    "unloading_platform": UNLOADING_PLATFORM_LAYOUT,
    "mobile_warehouse": MOBILE_WAREHOUSE_LAYOUT,
    "explosive": EXPLOSIVE_LAYOUT,
    "actual_layout_step": ACTUAL_LAYOUT_STEP_LAYOUT,
    "internal_layout": INTERNAL_LAYOUT,
    "sizing": SIZING_LAYOUT,
    "unit_spec": UNIT_PACKAGE_LAYOUT,
    "placement": PLACEMENT_LAYOUT,
    "berm": BERM_LAYOUT,
    "lightning": LIGHTNING_LAYOUT,
    "mast": MAST_LAYOUT,
    "target": TARGET_LAYOUT,
    "settings": SETTINGS_LAYOUT,
}

LAYOUT_MODELS = {
    "project": WarehouseProjectInput,
    "territory": WarehouseProjectInput,
    "storage_general": StorageBuilding,
    "building_placement": StorageBuilding,
    "sizing_step": StorageDesignInput,
    "lightning_step": StorageDesignInput,
    "unloading_platform": UnloadingPlatformConfig,
    "mobile_warehouse": MobileWarehouseConfig,
    "explosive": ExplosiveItem,
    "actual_layout_step": StorageBuilding,
    "internal_layout": InternalLayoutConfig,
    "sizing": StorageSizingInput,
    "unit_spec": UnitPackageSpec,
    "placement": StorageDesignInput,
    "berm": BermSpec,
    "lightning": LightningSpec,
    "mast": LightningArresterMast,
    "target": ExternalProtectedObject,
    "settings": CalculationSettings,
}

# Раскладка вложенных моделей по умолчанию: формы групп и таблиц строк берут ее автоматически.
MODEL_LAYOUTS: dict[type, FormLayout] = {
    StorageSizingInput: SIZING_LAYOUT,
    UnitPackageSpec: UNIT_PACKAGE_LAYOUT,
    BermSpec: BERM_LAYOUT,
    LightningSpec: LIGHTNING_LAYOUT,
    LightningArresterMast: MAST_LAYOUT,
    ExplosiveItem: EXPLOSIVE_LAYOUT,
    InternalLayoutConfig: INTERNAL_LAYOUT,
    ExternalProtectedObject: TARGET_LAYOUT,
    UnloadingPlatformConfig: UNLOADING_PLATFORM_LAYOUT,
    MobileWarehouseConfig: MOBILE_WAREHOUSE_LAYOUT,
    CalculationSettings: SETTINGS_LAYOUT,
}


def layout_for_model(model_cls: type) -> FormLayout | None:
    return MODEL_LAYOUTS.get(model_cls)
