"""Модели защитного обвалования (п. 602–605 Приказа № 343)."""

from pydantic import BaseModel, Field

from explosions_core.domain.base import InputModel
from explosions_core.domain.enums import BermSoilMaterial
from explosions_core.domain.results import NormativeViolation
from explosions_core.norms.constants_rk343 import (
    DEFAULT_BERM_SLOPE_ANGLE_DEG,
    DEFAULT_CREST_ELEVATION_ABOVE_LOAD_M,
    DEFAULT_ENTRANCE_OPENING_WIDTH_M,
    DEFAULT_SCREEN_OVERLAP_M,
    DEFAULT_WALL_TO_TOE_CLEARANCE_M,
    MAX_BERM_SLOPE_ANGLE_DEG,
    MIN_BERM_CREST_WIDTH_M,
    MIN_BERM_SLOPE_ANGLE_DEG,
)


class BermSpec(InputModel):
    """Параметры вала, не зависящие от габаритов здания и высоты груза."""

    crest_elevation_above_load_m: float = DEFAULT_CREST_ELEVATION_ABOVE_LOAD_M
    crest_width_m: float = Field(default=MIN_BERM_CREST_WIDTH_M, gt=0)
    soil_material: BermSoilMaterial
    natural_slope_angle_deg: float = Field(
        default=DEFAULT_BERM_SLOPE_ANGLE_DEG,
        ge=MIN_BERM_SLOPE_ANGLE_DEG,
        le=MAX_BERM_SLOPE_ANGLE_DEG,
    )
    wall_to_inner_toe_clearance_m: float = Field(default=DEFAULT_WALL_TO_TOE_CLEARANCE_M, ge=0)
    has_entrance_screen_berm: bool = True
    entrance_opening_width_m: float = Field(default=DEFAULT_ENTRANCE_OPENING_WIDTH_M, ge=0)
    screen_overlap_each_side_m: float = Field(default=DEFAULT_SCREEN_OVERLAP_M, ge=0)


class BermDesignInput(BermSpec):
    storage_length_m: float = Field(gt=0)
    storage_width_m: float = Field(gt=0)
    load_top_height_m: float = Field(gt=0, description="верхний уровень штабеля (стеллажа) с ВМ от пола, м (п. 604)")


class BermDesignResult(BaseModel):
    berm_height_m: float
    crest_width_m: float
    base_width_m: float
    cross_section_area_m2: float
    main_berm_centerline_length_m: float
    screen_berm_length_m: float
    screen_required_length_m: float | None = None
    total_earthwork_volume_m3: float
    outer_footprint_length_m: float
    outer_footprint_width_m: float
    violations: list[NormativeViolation] = Field(default_factory=list)
