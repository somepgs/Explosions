"""Доменная модель расчетного ядра: реэкспорт всех моделей и перечислений."""

from explosions_core.domain.berm import BermDesignInput, BermDesignResult, BermSpec
from explosions_core.domain.distances import DetonationPairResult, ExternalProtectedObject, UVVDistanceResult
from explosions_core.domain.enums import (
    BermSoilMaterial,
    ChargePlacementType,
    CompatibilityGroup,
    DetonationFormulaType,
    DetonationMaterialClass,
    LightningMethod,
    LightningProtectionLevel,
    LightningReliability,
    LightningZoneType,
    LocationType,
    PackagingType,
    StorageMethod,
    UVVMethod,
    WarehouseCategory,
    WarehouseDuration,
)
from explosions_core.domain.explosives import ExplosiveItem, UnitPackageSpec
from explosions_core.domain.lightning import CheckPoint3D, LightningArresterMast, LightningProtectionResult
from explosions_core.domain.project import (
    CalculationIssue,
    CalculationSettings,
    LightningSpec,
    ProjectCalculationResult,
    ProjectDefinition,
    StorageDesignInput,
)
from explosions_core.domain.records import BermRecord, LightningRecord, StorageSizingRecord
from explosions_core.domain.results import NormativeViolation, ValidationResult
from explosions_core.domain.sizing import StorageSizingInput, StorageSizingResult
from explosions_core.domain.storage import (
    BermParams,
    InternalLayoutConfig,
    MobileWarehouseConfig,
    StorageBuilding,
    UnloadingPlatformConfig,
    WarehouseProjectInput,
)

__all__ = [
    "BermDesignInput",
    "BermDesignResult",
    "BermParams",
    "BermRecord",
    "BermSoilMaterial",
    "BermSpec",
    "CalculationIssue",
    "CalculationSettings",
    "ChargePlacementType",
    "CheckPoint3D",
    "CompatibilityGroup",
    "DetonationFormulaType",
    "DetonationMaterialClass",
    "DetonationPairResult",
    "ExplosiveItem",
    "ExternalProtectedObject",
    "InternalLayoutConfig",
    "LightningArresterMast",
    "LightningMethod",
    "LightningProtectionLevel",
    "LightningProtectionResult",
    "LightningRecord",
    "LightningReliability",
    "LightningSpec",
    "LightningZoneType",
    "LocationType",
    "MobileWarehouseConfig",
    "NormativeViolation",
    "PackagingType",
    "ProjectCalculationResult",
    "ProjectDefinition",
    "StorageBuilding",
    "StorageDesignInput",
    "StorageMethod",
    "StorageSizingInput",
    "StorageSizingRecord",
    "StorageSizingResult",
    "UVVDistanceResult",
    "UVVMethod",
    "UnitPackageSpec",
    "UnloadingPlatformConfig",
    "ValidationResult",
    "WarehouseCategory",
    "WarehouseDuration",
    "WarehouseProjectInput",
]
