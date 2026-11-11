"""Файл проекта склада ВМ и результат полного расчета конвейера."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from explosions_core.domain.base import InputModel
from explosions_core.domain.berm import BermDesignResult, BermSpec
from explosions_core.domain.distances import DetonationPairResult, UVVDistanceResult
from explosions_core.domain.enums import (
    ChargePlacementType,
    DetonationFormulaType,
    LightningMethod,
    LightningProtectionLevel,
    LightningReliability,
    LightningZoneType,
    UVVMethod,
)
from explosions_core.domain.lightning import LightningArresterMast
from explosions_core.domain.records import BermRecord, LightningRecord, StorageSizingRecord
from explosions_core.domain.results import NormativeViolation, ValidationResult
from explosions_core.domain.sizing import StorageSizingInput
from explosions_core.domain.storage import WarehouseProjectInput
from explosions_core.norms.constants_rk343 import (
    DEFAULT_LIGHTNING_PROTECTION_LEVEL,
    DEFAULT_SO153_RELIABILITY,
    DEFAULT_WALL_THICKNESS_M,
)

PROJECT_SCHEMA_VERSION = "1"


class LightningSpec(InputModel):
    """Молниезащита хранилища. Координаты мачт — относительно центра здания.

    По умолчанию — катящаяся сфера СП РК 2.04-103-2013 уровня I. Метод `single_rod_so_153` — зоны по
    табл. 3.4 СО 153-34.21.122-2003 с надежностью `reliability`. Зоны РД 34.21.122-87 задаются
    методом `zones_rd_34_21_122` и обязательным типом зоны `zone_type`.
    """

    method: LightningMethod = LightningMethod.ROLLING_SPHERE_SP_RK
    protection_level: LightningProtectionLevel = Field(
        default=LightningProtectionLevel(DEFAULT_LIGHTNING_PROTECTION_LEVEL),
    )
    reliability: LightningReliability = Field(default=LightningReliability(DEFAULT_SO153_RELIABILITY))
    zone_type: LightningZoneType | None = None
    masts: list[LightningArresterMast] = Field(min_length=1)
    vent_height_m: float | None = Field(default=None, gt=0)

    @model_validator(mode="before")
    @classmethod
    def _zone_type_without_method_means_rd(cls, data):
        """Файлы проекта до задания № 10 содержат только zone_type: считаются по зонам РД 34.21.122-87, как раньше."""
        if isinstance(data, dict) and data.get("zone_type") is not None and data.get("method") is None:
            return {**data, "method": LightningMethod.ZONES_RD_34_21_122}
        return data


class StorageDesignInput(InputModel):
    """Проектные данные хранилища, связанные с записью `StorageBuilding` по `storage_id`."""

    storage_id: str
    sizing: StorageSizingInput | None = None
    eaves_height_m: float | None = Field(default=None, gt=0)
    ridge_height_m: float | None = Field(default=None, gt=0)
    load_top_height_m: float | None = Field(
        default=None,
        gt=0,
        description="верхний уровень штабеля (стеллажа) для п. 604; если не задан — берется из расчета sizing",
    )
    berm: BermSpec | None = None
    lightning: LightningSpec | None = None


class CalculationSettings(InputModel):
    detonation_formula: DetonationFormulaType = DetonationFormulaType.MAX_CONSERVATIVE
    uvv_placement: ChargePlacementType | None = Field(
        default=None,
        description="принудительное расположение заряда для УВВ; None — по типу хранилища и степени повреждения (п. 10)",
    )
    uvv_method: UVVMethod = UVVMethod.TABLE_2_FORMULAS
    wall_thickness_m: float = Field(default=DEFAULT_WALL_THICKNESS_M, gt=0)


class ProjectDefinition(InputModel):
    """Файл проекта: единственный входной документ конвейера расчета."""

    schema_version: Literal["1"] = PROJECT_SCHEMA_VERSION
    project: WarehouseProjectInput
    storage_designs: list[StorageDesignInput] = Field(default_factory=list)
    settings: CalculationSettings = Field(default_factory=CalculationSettings)


class CalculationIssue(BaseModel):
    """Замечание или ошибка расчета модуля. Ошибка модуля не прерывает расчет остальных."""

    model_config = ConfigDict(frozen=True)

    severity: Literal["error", "warning"]
    module: str
    object_id: str | None = None
    message: str


class ProjectCalculationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    project: WarehouseProjectInput
    validation: ValidationResult
    sizing_records: list[StorageSizingRecord] = Field(default_factory=list)
    berm_records: list[BermRecord] = Field(default_factory=list)
    lightning_records: list[LightningRecord] = Field(default_factory=list)
    detonation_results: list[DetonationPairResult] = Field(default_factory=list)
    uvv_results: list[UVVDistanceResult] = Field(default_factory=list)
    issues: list[CalculationIssue] = Field(default_factory=list)
    settings: CalculationSettings = Field(
        default_factory=CalculationSettings,
        description="настройки, с которыми выполнен расчет (методы, толщина стен для чертежей)",
    )

    @property
    def all_violations(self) -> list[NormativeViolation]:
        violations: list[NormativeViolation] = list(self.validation.violations)
        for record in self.sizing_records:
            violations.extend(record.result.violations)
        for berm in self.berm_records:
            violations.extend(berm.result.violations)
        for lightning in self.lightning_records:
            violations.extend(lightning.result.violations)
        for pair in self.detonation_results:
            violations.extend(pair.violations)
        for uvv in self.uvv_results:
            violations.extend(uvv.violations)
        return violations

    @property
    def errors(self) -> list[CalculationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def is_compliant(self) -> bool:
        return not self.all_violations and not self.errors

    @property
    def berm_results_by_storage(self) -> dict[str, BermDesignResult]:
        return {record.storage_id: record.result for record in self.berm_records}
