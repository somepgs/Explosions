"""Записи расчетов по хранилищу: результаты модулей с исходными данными, передаваемые в выходные генераторы."""

from pydantic import BaseModel, ConfigDict

from explosions_core.domain.berm import BermDesignInput, BermDesignResult
from explosions_core.domain.enums import (
    LightningMethod,
    LightningProtectionLevel,
    LightningReliability,
    LightningZoneType,
)
from explosions_core.domain.lightning import LightningArresterMast, LightningProtectionResult
from explosions_core.domain.sizing import StorageSizingInput, StorageSizingResult


class StorageSizingRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    storage_id: str
    sizing_input: StorageSizingInput
    result: StorageSizingResult


class BermRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    storage_id: str
    berm_input: BermDesignInput
    result: BermDesignResult


class LightningRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    storage_id: str
    method: LightningMethod = LightningMethod.ROLLING_SPHERE_SP_RK
    protection_level: LightningProtectionLevel = LightningProtectionLevel.LEVEL_I
    reliability: LightningReliability = LightningReliability.P_0_999
    zone_type: LightningZoneType | None = None
    masts: list[LightningArresterMast]
    storage_length_m: float
    storage_width_m: float
    eaves_height_m: float
    ridge_height_m: float
    vent_height_m: float | None = None
    result: LightningProtectionResult
