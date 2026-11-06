"""Модели молниезащиты (СП РК 2.04-103-2013, п. 8.1.1)."""

from pydantic import BaseModel, Field

from explosions_core.domain.enums import LightningZoneType
from explosions_core.domain.results import NormativeViolation
from explosions_core.norms.constants_rk343 import MAX_ROD_ARRESTER_HEIGHT_M


class LightningArresterMast(BaseModel):
    mast_id: str
    x_m: float
    y_m: float
    height_h_m: float = Field(gt=0, le=MAX_ROD_ARRESTER_HEIGHT_M)


class CheckPoint3D(BaseModel):
    name: str
    x_m: float
    y_m: float
    z_height_m: float = Field(ge=0)


class LightningProtectionResult(BaseModel):
    zone_type: LightningZoneType
    mast_results: list[dict] = Field(default_factory=list)
    min_recommended_mast_height_m: float | None = None
    unprotected_points: list[str] = Field(default_factory=list)
    is_fully_protected: bool
    violations: list[NormativeViolation] = Field(default_factory=list)
