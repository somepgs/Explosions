"""Расчет количества мест тары и минимальных внутренних габаритов хранилища ВМ (п. 579-580 Приказа МИР РК № 343)."""

import math
from dataclasses import dataclass

from explosions_core.domain import (
    CompatibilityGroup,
    NormativeViolation,
    PackagingType,
    StorageMethod,
    StorageSizingInput,
    StorageSizingResult,
)
from explosions_core.norms.constants_rk343 import (
    MAX_PALLET_TIERS_COUNT,
    MAX_RACK_SHELF_HEIGHT_OTHER_M,
    MAX_RACK_SHELF_HEIGHT_UNSEALED_BC_M,
    MAX_RACK_WIDTH_UNITS_ISLAND,
    MAX_RACK_WIDTH_UNITS_WALL,
    MAX_STACK_HEIGHT_PALLET_M,
    MAX_STACK_HEIGHT_STANDARD_M,
    MAX_STACK_WIDTH_UNITS,
    MAX_TIERS_OTHER,
    MAX_TIERS_UNSEALED_BC,
    MIN_AISLE_WIDTH_RACK_M,
    MIN_AISLE_WIDTH_STACK_M,
    MIN_CEILING_CLEARANCE_ABOVE_LOAD_M,
    MIN_FLOOR_DECK_HEIGHT_M,
    MIN_SHELF_VERTICAL_GAP_M,
    MIN_WALL_CLEARANCE_M,
)
from explosions_core.norms.references import CLAUSE_RACK, CLAUSE_STACK

_EPS = 1e-9


def _floor(value: float) -> int:
    return math.floor(value + _EPS)


def _ceil(value: float) -> int:
    return math.ceil(value - _EPS)


@dataclass(frozen=True)
class _Layout:
    tiers_per_shelf: int
    shelves_or_tiers_count: int
    shelf_step_height_m: float | None
    top_shelf_height_m: float | None
    loaded_height_m: float
    units_per_cross_section: int
    wall_racks_count: int
    wall_rack_depth_m: float
    line_depth_m: float
    aisle_width_m: float


class StorageSizingCalculator:
    def calculate(self, data: StorageSizingInput) -> StorageSizingResult:
        violations: list[NormativeViolation] = []
        self._check_common_norms(data, violations)
        if data.storage_method == StorageMethod.RACK:
            layout = self._rack_layout(data, violations)
        else:
            layout = self._stack_layout(data, violations)

        spec = data.unit_spec
        total_units = _ceil(data.total_net_explosive_mass_kg / spec.net_weight_kg)

        total_lines = layout.wall_racks_count + data.island_rows_count
        longitudinal_aisles = max(1, total_lines - 1)
        b_aisle = layout.aisle_width_m
        internal_width = (
            2 * data.wall_clearance_m
            + layout.wall_racks_count * layout.wall_rack_depth_m
            + data.island_rows_count * layout.line_depth_m
            + longitudinal_aisles * b_aisle
        )

        units_along_line = 0
        if layout.units_per_cross_section > 0:
            units_along_line = max(
                _ceil(total_units / layout.units_per_cross_section),
                data.preferred_units_along_single_line or 0,
            )
        line_length = units_along_line * spec.length_m + max(0, units_along_line - 1) * spec.unit_gap_m
        internal_length = 2 * data.wall_clearance_m + line_length + data.cross_aisles_count * b_aisle
        internal_height = layout.loaded_height_m + MIN_CEILING_CLEARANCE_ABOVE_LOAD_M

        useful_area = (
            layout.wall_racks_count * layout.wall_rack_depth_m + data.island_rows_count * layout.line_depth_m
        ) * line_length
        total_area = internal_width * internal_length
        utilization = useful_area / total_area if total_area > 0 else 0.0

        return StorageSizingResult(
            total_units_required=total_units,
            total_gross_weight_kg=total_units * spec.gross_weight_kg,
            shelves_or_tiers_count=layout.shelves_or_tiers_count,
            tiers_per_shelf=layout.tiers_per_shelf,
            shelf_step_height_m=layout.shelf_step_height_m,
            top_shelf_height_m=layout.top_shelf_height_m,
            total_loaded_height_m=layout.loaded_height_m,
            required_aisle_width_m=b_aisle,
            line_length_m=line_length,
            min_internal_width_m=internal_width,
            min_internal_length_m=internal_length,
            min_internal_height_m=internal_height,
            useful_storage_area_m2=useful_area,
            total_internal_area_m2=total_area,
            area_utilization_coeff=utilization,
            units_per_cross_section=layout.units_per_cross_section,
            units_along_line=units_along_line,
            wall_rack_depth_m=layout.wall_rack_depth_m,
            island_line_depth_m=layout.line_depth_m,
            violations=violations,
        )

    @staticmethod
    def _check_common_norms(data: StorageSizingInput, violations: list[NormativeViolation]) -> None:
        if data.storage_method == StorageMethod.RACK and data.shelf_vertical_gap_m < MIN_SHELF_VERTICAL_GAP_M - _EPS:
            violations.append(
                NormativeViolation(
                    code="SHELF_VERTICAL_GAP",
                    clause=CLAUSE_RACK,
                    description="Зазор между верхом тары и нижней плоскостью полки над ней меньше минимального",
                    actual_value=data.shelf_vertical_gap_m,
                    required_value=MIN_SHELF_VERTICAL_GAP_M,
                )
            )
        if data.floor_deck_height_m < MIN_FLOOR_DECK_HEIGHT_M - _EPS:
            violations.append(
                NormativeViolation(
                    code="FLOOR_DECK_HEIGHT",
                    clause=CLAUSE_STACK,
                    description="Высота настила или нижней полки от пола меньше минимальной",
                    actual_value=data.floor_deck_height_m,
                    required_value=MIN_FLOOR_DECK_HEIGHT_M,
                )
            )
        if data.wall_clearance_m < MIN_WALL_CLEARANCE_M - _EPS:
            violations.append(
                NormativeViolation(
                    code="WALL_CLEARANCE",
                    clause=CLAUSE_STACK,
                    description="Отступ стеллажей и штабелей от стен меньше минимального",
                    actual_value=data.wall_clearance_m,
                    required_value=MIN_WALL_CLEARANCE_M,
                )
            )

    @staticmethod
    def _rack_layout(data: StorageSizingInput, violations: list[NormativeViolation]) -> _Layout:
        spec = data.unit_spec
        if data.is_unsealed and (
            data.compatibility_group in (CompatibilityGroup.B, CompatibilityGroup.C) or data.is_black_powder
        ):
            tiers = MAX_TIERS_UNSEALED_BC
            max_top_shelf_h = MAX_RACK_SHELF_HEIGHT_UNSEALED_BC_M
        else:
            tiers = MAX_TIERS_OTHER
            max_top_shelf_h = MAX_RACK_SHELF_HEIGHT_OTHER_M
            if data.floor_deck_height_m + tiers * spec.height_m > max_top_shelf_h + _EPS:
                tiers = MAX_TIERS_UNSEALED_BC

        shelf_step = tiers * spec.height_m + data.shelf_vertical_gap_m + data.shelf_thickness_m
        available = max_top_shelf_h - data.floor_deck_height_m
        shelves = _floor(available / shelf_step) + 1 if available >= -_EPS else 0

        top_shelf = data.floor_deck_height_m + (shelves - 1) * shelf_step if shelves > 0 else None
        loaded = top_shelf + tiers * spec.height_m if top_shelf is not None else 0.0
        if shelves == 0:
            violations.append(
                NormativeViolation(
                    code="RACK_SHELF_NOT_FIT",
                    clause=CLAUSE_RACK,
                    description="Ни одна полка с ярусами тары не помещается под предельную высоту верхней полки",
                    actual_value=data.floor_deck_height_m + tiers * spec.height_m,
                    required_value=max_top_shelf_h,
                )
            )

        wall_depth = MAX_RACK_WIDTH_UNITS_WALL * spec.width_m + (MAX_RACK_WIDTH_UNITS_WALL - 1) * spec.unit_gap_m
        island_depth = MAX_RACK_WIDTH_UNITS_ISLAND * spec.width_m + (MAX_RACK_WIDTH_UNITS_ISLAND - 1) * spec.unit_gap_m
        units_per_cross_section = shelves * tiers * (
            data.wall_racks_count * MAX_RACK_WIDTH_UNITS_WALL + data.island_rows_count * MAX_RACK_WIDTH_UNITS_ISLAND
        )
        return _Layout(
            tiers_per_shelf=tiers,
            shelves_or_tiers_count=shelves,
            shelf_step_height_m=shelf_step,
            top_shelf_height_m=top_shelf,
            loaded_height_m=loaded,
            units_per_cross_section=units_per_cross_section,
            wall_racks_count=data.wall_racks_count,
            wall_rack_depth_m=wall_depth,
            line_depth_m=island_depth,
            aisle_width_m=MIN_AISLE_WIDTH_RACK_M,
        )

    @staticmethod
    def _stack_layout(data: StorageSizingInput, violations: list[NormativeViolation]) -> _Layout:
        spec = data.unit_spec
        if data.packaging_type in (PackagingType.PALLET, PackagingType.CONTAINER):
            if not data.is_mechanized:
                violations.append(
                    NormativeViolation(
                        code="MECHANIZATION_REQUIRED",
                        clause=CLAUSE_STACK,
                        description="Хранение на поддонах и в стропконтейнерах допускается только при использовании средств механизации",
                        actual_value="без средств механизации",
                        required_value="со средствами механизации",
                    )
                )
            max_stack_h = MAX_STACK_HEIGHT_PALLET_M
            tiers = min(
                MAX_PALLET_TIERS_COUNT,
                max(0, _floor((max_stack_h - data.floor_deck_height_m) / spec.height_m)),
            )
            width_units = MAX_STACK_WIDTH_UNITS if data.packaging_type == PackagingType.PALLET else 1
        else:
            max_stack_h = MAX_STACK_HEIGHT_STANDARD_M
            tiers = max(0, _floor((max_stack_h - data.floor_deck_height_m) / spec.height_m))
            width_units = MAX_STACK_WIDTH_UNITS

        if tiers == 0:
            violations.append(
                NormativeViolation(
                    code="STACK_TIER_NOT_FIT",
                    clause=CLAUSE_STACK,
                    description="Ни один ярус тары не помещается под предельную высоту штабеля",
                    actual_value=data.floor_deck_height_m + spec.height_m,
                    required_value=max_stack_h,
                )
            )

        loaded = data.floor_deck_height_m + tiers * spec.height_m if tiers > 0 else 0.0
        stack_depth = width_units * spec.width_m + (width_units - 1) * spec.unit_gap_m
        units_per_cross_section = tiers * width_units * data.island_rows_count
        return _Layout(
            tiers_per_shelf=1,
            shelves_or_tiers_count=tiers,
            shelf_step_height_m=None,
            top_shelf_height_m=None,
            loaded_height_m=loaded,
            units_per_cross_section=units_per_cross_section,
            wall_racks_count=0,
            wall_rack_depth_m=0.0,
            line_depth_m=stack_depth,
            aisle_width_m=MIN_AISLE_WIDTH_STACK_M,
        )


def calculate_storage_size(data: StorageSizingInput) -> StorageSizingResult:
    return StorageSizingCalculator().calculate(data)
