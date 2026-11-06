"""Модели взрывчатых материалов и тары."""

from pydantic import BaseModel, Field

from explosions_core.domain.base import InputModel
from explosions_core.domain.enums import CompatibilityGroup, DetonationMaterialClass
from explosions_core.norms.constants_rk343 import DEFAULT_UNIT_GAP_M


class ExplosiveItem(InputModel):
    name: str
    group: CompatibilityGroup
    mass_kg: float = Field(ge=0)
    si_count: int = Field(default=0, ge=0)
    is_initiating_device: bool = False
    is_black_powder: bool = False
    is_smokeless_powder: bool = False
    tnt_equivalent_coeff: float | None = Field(default=None, ge=0)
    hazard_subclass: str | None = None
    detonation_class: DetonationMaterialClass | None = None
    is_detonating_cord: bool = False

    @property
    def net_explosive_mass_kg(self) -> float:
        return self.mass_kg


class UnitPackageSpec(InputModel):
    net_weight_kg: float = Field(gt=0)
    gross_weight_kg: float = Field(gt=0)
    length_m: float = Field(gt=0)
    width_m: float = Field(gt=0)
    height_m: float = Field(gt=0)
    unit_gap_m: float = Field(default=DEFAULT_UNIT_GAP_M, ge=0)
