"""Модели безопасных расстояний по УВВ и передаче детонации."""

from pydantic import BaseModel, Field

from explosions_core.domain.results import NormativeViolation
from explosions_core.norms.constants_rk343 import MAX_TOPOGRAPHY_REDUCTION_COEFF, MIN_TOPOGRAPHY_REDUCTION_COEFF


class ExternalProtectedObject(BaseModel):
    object_id: str
    name: str
    allowed_damage_degree: int = Field(ge=1, le=5)
    custom_kv_override: float | None = Field(default=None, gt=0)
    actual_distance_m: float = Field(ge=0)
    topography_reduction_coeff: float = Field(
        default=MAX_TOPOGRAPHY_REDUCTION_COEFF,
        ge=MIN_TOPOGRAPHY_REDUCTION_COEFF,
        le=MAX_TOPOGRAPHY_REDUCTION_COEFF,
    )
    bearing_deg: float | None = Field(default=None, ge=0, lt=360)


class UVVDistanceResult(BaseModel):
    storage_id: str
    object_id: str
    equivalent_tnt_mass_kg: float
    formula_used: str
    applied_coeff_kv: float
    required_distance_m: float
    actual_distance_m: float
    safety_margin_m: float
    is_safe: bool
    violations: list[NormativeViolation] = Field(default_factory=list)


class DetonationPairResult(BaseModel):
    storage_i_id: str
    storage_j_id: str
    q_i_tnt_kg: float
    q_j_tnt_kg: float
    r_d_i_to_j_m: float
    r_d_j_to_i_m: float
    governing_required_r_d_m: float
    actual_clear_distance_m: float
    is_safe: bool
    violations: list[NormativeViolation] = Field(default_factory=list)
