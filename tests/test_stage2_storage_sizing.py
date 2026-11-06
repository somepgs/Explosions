import pytest

from explosions_core.calc.storage_sizing import StorageSizingCalculator
from explosions_core.domain import CompatibilityGroup, PackagingType, StorageMethod, StorageSizingInput

BAG_SPEC = {"net_weight_kg": 25.0, "gross_weight_kg": 26.0, "length_m": 0.55, "width_m": 0.35, "height_m": 0.15}
PALLET_SPEC = {"net_weight_kg": 1000.0, "gross_weight_kg": 1100.0, "length_m": 1.2, "width_m": 0.8, "height_m": 1.1}


def _make_input(**overrides) -> StorageSizingInput:
    data = {
        "total_net_explosive_mass_kg": 40000.0,
        "compatibility_group": CompatibilityGroup.D,
        "storage_method": StorageMethod.STACK,
        "packaging_type": PackagingType.BAG,
        "unit_spec": dict(BAG_SPEC),
        "island_rows_count": 4,
    }
    data.update(overrides)
    return StorageSizingInput(**data)


def _calc(**overrides):
    return StorageSizingCalculator().calculate(_make_input(**overrides))


def _codes(result) -> list[str]:
    return [v.code for v in result.violations]


def test_units_and_gross_weight_from_mass():
    result = _calc()

    assert result.total_units_required == 1600
    assert result.total_gross_weight_kg == pytest.approx(1600 * 26.0)


def test_partial_unit_rounds_up():
    result = _calc(total_net_explosive_mass_kg=40001.0)

    assert result.total_units_required == 1601


def test_bag_stack_scenario_matches_clause_579_geometry():
    result = _calc()

    assert result.violations == []
    assert result.shelves_or_tiers_count == 12
    assert result.total_loaded_height_m == pytest.approx(1.9)
    assert result.total_loaded_height_m <= 2.0
    assert result.required_aisle_width_m == pytest.approx(1.3)
    assert result.units_per_cross_section == 96
    assert result.units_along_line == 17
    assert result.line_length_m == pytest.approx(9.67)
    assert result.min_internal_width_m == pytest.approx(7.18)
    assert result.min_internal_length_m == pytest.approx(12.67)
    assert result.min_internal_height_m == pytest.approx(2.4)
    assert result.total_internal_area_m2 == pytest.approx(7.18 * 12.67)
    assert result.useful_storage_area_m2 == pytest.approx(4 * 0.72 * 9.67)
    assert result.area_utilization_coeff == pytest.approx((4 * 0.72 * 9.67) / (7.18 * 12.67))


def test_preferred_units_along_line_extends_length():
    result = _calc(preferred_units_along_single_line=20)

    assert result.units_along_line == 20
    assert result.line_length_m == pytest.approx(20 * 0.55 + 19 * 0.02)


def test_unsealed_group_b_rack_uses_single_tier_and_top_shelf_within_1_7_m():
    result = _calc(
        storage_method=StorageMethod.RACK,
        packaging_type=PackagingType.BOX,
        compatibility_group=CompatibilityGroup.B,
        is_unsealed=True,
        island_rows_count=2,
        wall_racks_count=1,
    )

    assert result.tiers_per_shelf == 1
    assert result.shelf_step_height_m == pytest.approx(0.23)
    assert result.shelves_or_tiers_count == 7
    assert result.top_shelf_height_m == pytest.approx(1.48)
    assert result.top_shelf_height_m <= 1.7 + 1e-9
    assert result.violations == []


def test_unsealed_black_powder_rack_uses_single_tier():
    result = _calc(
        storage_method=StorageMethod.RACK,
        packaging_type=PackagingType.BOX,
        compatibility_group=CompatibilityGroup.D,
        is_black_powder=True,
        is_unsealed=True,
        island_rows_count=2,
    )

    assert result.tiers_per_shelf == 1
    assert result.top_shelf_height_m <= 1.7 + 1e-9


def test_wall_rack_without_aisle_counts_one_row_width():
    result = _calc(
        storage_method=StorageMethod.RACK,
        packaging_type=PackagingType.BOX,
        compatibility_group=CompatibilityGroup.B,
        is_unsealed=True,
        island_rows_count=2,
        wall_racks_count=1,
    )

    assert result.wall_rack_depth_m == pytest.approx(0.35)
    assert result.island_line_depth_m == pytest.approx(2 * 0.35 + 0.02)


def test_sealed_rack_allows_two_tiers_with_top_shelf_within_2_m():
    result = _calc(
        storage_method=StorageMethod.RACK,
        packaging_type=PackagingType.BOX,
        compatibility_group=CompatibilityGroup.D,
        island_rows_count=2,
        wall_racks_count=0,
    )

    assert result.tiers_per_shelf == 2
    assert result.shelves_or_tiers_count == 6
    assert result.top_shelf_height_m == pytest.approx(2.0)
    assert result.top_shelf_height_m <= 2.0 + 1e-9


def test_stack_ignores_wall_racks():
    result = _calc(wall_racks_count=2)

    assert result.wall_rack_depth_m == 0.0
    assert result.violations == []


def test_pallet_stack_limited_to_two_tiers_and_2_6_m_when_mechanized():
    result = _calc(
        packaging_type=PackagingType.PALLET,
        is_mechanized=True,
        unit_spec=dict(PALLET_SPEC),
        total_net_explosive_mass_kg=10000.0,
    )

    assert result.violations == []
    assert result.shelves_or_tiers_count == 2
    assert result.total_loaded_height_m == pytest.approx(2.3)
    assert result.total_loaded_height_m <= 2.6


def test_pallet_tiers_never_exceed_two_even_for_low_units():
    low_spec = dict(PALLET_SPEC, height_m=0.5)
    result = _calc(
        packaging_type=PackagingType.PALLET,
        is_mechanized=True,
        unit_spec=low_spec,
        total_net_explosive_mass_kg=10000.0,
    )

    assert result.shelves_or_tiers_count == 2
    assert result.total_loaded_height_m == pytest.approx(1.1)


def test_pallet_stack_without_mechanization_is_violation():
    result = _calc(
        packaging_type=PackagingType.PALLET,
        is_mechanized=False,
        unit_spec=dict(PALLET_SPEC),
        total_net_explosive_mass_kg=10000.0,
    )

    violation = next(v for v in result.violations if v.code == "MECHANIZATION_REQUIRED")
    assert "п. 579" in violation.clause


def test_container_stack_uses_single_row_width():
    result = _calc(
        packaging_type=PackagingType.CONTAINER,
        is_mechanized=True,
        unit_spec=dict(PALLET_SPEC),
        total_net_explosive_mass_kg=10000.0,
    )

    assert result.island_line_depth_m == pytest.approx(0.8)
    assert result.units_per_cross_section == 2 * 1 * 4


def test_shelf_vertical_gap_below_norm_is_violation():
    result = _calc(
        storage_method=StorageMethod.RACK,
        packaging_type=PackagingType.BOX,
        island_rows_count=2,
        shelf_vertical_gap_m=0.02,
    )

    violation = next(v for v in result.violations if v.code == "SHELF_VERTICAL_GAP")
    assert "п. 580" in violation.clause
    assert violation.actual_value == pytest.approx(0.02)
    assert violation.required_value == pytest.approx(0.04)


def test_wall_clearance_below_norm_is_violation():
    result = _calc(wall_clearance_m=0.1)

    assert "WALL_CLEARANCE" in _codes(result)


def test_floor_deck_below_norm_is_violation():
    result = _calc(floor_deck_height_m=0.05)

    assert "FLOOR_DECK_HEIGHT" in _codes(result)


def test_unit_taller_than_stack_limit_gives_zero_capacity_violation():
    result = _calc(
        packaging_type=PackagingType.BOX,
        unit_spec=dict(BAG_SPEC, height_m=2.5),
    )

    assert "STACK_TIER_NOT_FIT" in _codes(result)
    assert result.total_units_required == 1600
    assert result.units_along_line == 0
    assert result.line_length_m == 0.0


def test_wall_racks_alias_is_accepted():
    model = _make_input(wall_Reifen_rows_count=1)

    assert model.wall_racks_count == 1
