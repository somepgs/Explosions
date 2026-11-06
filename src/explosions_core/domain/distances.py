"""Модели безопасных расстояний по УВВ и передаче детонации."""

from pydantic import BaseModel, Field

from explosions_core.domain.base import InputModel
from explosions_core.domain.enums import ChargePlacementType, UVVMethod
from explosions_core.domain.results import NormativeViolation
from explosions_core.norms.constants_rk343 import MAX_TOPOGRAPHY_REDUCTION_COEFF, MIN_TOPOGRAPHY_REDUCTION_COEFF


class ExternalProtectedObject(InputModel):
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
    table3_object_category: int | None = Field(
        default=None,
        ge=1,
        le=3,
        description="категория объекта по таблице 3 Приложения 11 (нужна для метода table_3)",
    )


class UVVDistanceResult(BaseModel):
    storage_id: str
    object_id: str
    method: UVVMethod = UVVMethod.TABLE_2_FORMULAS
    explosive_mass_kg: float
    placement: ChargePlacementType
    formula_used: str
    kv_range: tuple[float, float] | None = None
    applied_coeff: float
    required_distance_m: float
    actual_distance_m: float
    safety_margin_m: float
    is_safe: bool
    violations: list[NormativeViolation] = Field(default_factory=list)


class DetonationPairResult(BaseModel):
    storage_i_id: str
    storage_j_id: str
    q_i_kg: float
    q_j_kg: float
    k_d_i_to_j: float
    k_d_j_to_i: float
    b_i_m: float
    b_j_m: float
    r_d_i_to_j_m: float
    r_d_j_to_i_m: float
    governing_required_r_d_m: float
    actual_clear_distance_m: float
    axial_min_distance_m: float | None = None
    is_safe: bool
    violations: list[NormativeViolation] = Field(default_factory=list)
