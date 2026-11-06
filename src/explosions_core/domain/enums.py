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
    F = "F"
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
    BURIED_OWN_HEIGHT = "buried_own_height"


class DetonationMaterialClass(str, Enum):
    AN_BASED = "an_based"
    NITROESTER_40_PLUS = "nitroester_40_plus"
    TNT = "tnt"
    DETONATORS = "detonators"


class DetonationFormulaType(str, Enum):
    FORMULA_19 = "formula_19"
    TABLE_5 = "table_5"
    MAX_CONSERVATIVE = "max_conservative"


class BermSoilMaterial(str, Enum):
    PLASTIC_CLAY_LOAM = "plastic_clay_loam"
    SANDY_FREE_FLOWING = "sandy_free_flowing"
    STONE_OR_GRAVEL = "stone_or_gravel"
    COMBUSTIBLE_MATERIAL = "combustible_material"


class LightningZoneType(str, Enum):
    ZONE_A = "zone_a"
    ZONE_B = "zone_b"


class LightningMethod(str, Enum):
    ROLLING_SPHERE_SP_RK = "rolling_sphere_sp_rk"
    SINGLE_ROD_SO_153 = "single_rod_so_153"
    ZONES_RD_34_21_122 = "zones_rd_34_21_122"


class LightningReliability(str, Enum):
    P_0_9 = "0.9"
    P_0_99 = "0.99"
    P_0_999 = "0.999"


class LightningProtectionLevel(str, Enum):
    LEVEL_I = "I"
    LEVEL_II = "II"
    LEVEL_III = "III"


class UVVMethod(str, Enum):
    TABLE_2_FORMULAS = "table_2_formulas"
    TABLE_3 = "table_3"
