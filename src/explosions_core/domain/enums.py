"""Перечисления доменной модели расчетного ядра."""

from enum import Enum


class WarehouseCategory(str, Enum):
    BASIS = "basis"
    EXPENDABLE = "expendable"


class WarehouseDuration(str, Enum):
    PERMANENT = "permanent"
    TEMPORARY = "temporary"
    SHORT_TERM = "short_term"
    MOBILE = "mobile"


class LocationType(str, Enum):
    SURFACE = "surface"
    SEMI_BURIED = "semi_buried"
    BURIED = "buried"
    UNDERGROUND = "underground"


class CompatibilityGroup(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    G = "G"
    N = "N"
    S = "S"


class PackagingType(str, Enum):
    BOX = "box"
    BAG = "bag"
    PALLET = "pallet"
    CONTAINER = "container"


class StorageMethod(str, Enum):
    RACK = "rack"
    STACK = "stack"


class ChargePlacementType(str, Enum):
    OPEN_SURFACE = "open_surface"
    SOIL_COVERED_1_5M = "soil_covered_1_5m"


class DetonationFormulaType(str, Enum):
    FORMULA_18_CUBIC = "formula_18_cubic"
    FORMULA_19_STACK_WIDTH = "formula_19_stack_width"
    MAX_CONSERVATIVE = "max_conservative"


class BermSoilMaterial(str, Enum):
    PLASTIC_CLAY_LOAM = "plastic_clay_loam"
    SANDY_FREE_FLOWING = "sandy_free_flowing"
    STONE_OR_GRAVEL = "stone_or_gravel"
    COMBUSTIBLE_MATERIAL = "combustible_material"


class LightningZoneType(str, Enum):
    ZONE_A = "zone_a"
    ZONE_B = "zone_b"
