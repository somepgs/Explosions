"""Записи расчетов, которые передаются в генератор расчетно-пояснительной записки."""

from dataclasses import dataclass

from explosions_core.domain import (
    BermDesignInput,
    BermDesignResult,
    LightningArresterMast,
    LightningProtectionResult,
    LightningZoneType,
    StorageSizingInput,
    StorageSizingResult,
)


@dataclass(frozen=True)
class StorageSizingRecord:
    storage_id: str
    sizing_input: StorageSizingInput
    result: StorageSizingResult


@dataclass(frozen=True)
class BermRecord:
    storage_id: str
    berm_input: BermDesignInput
    result: BermDesignResult


@dataclass(frozen=True)
class LightningRecord:
    storage_id: str
    zone_type: LightningZoneType
    masts: list[LightningArresterMast]
    storage_length_m: float
    storage_width_m: float
    eaves_height_m: float
    ridge_height_m: float
    result: LightningProtectionResult
