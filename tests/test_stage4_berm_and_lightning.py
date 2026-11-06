import pytest

from explosions_core.calc.berm_calculator import calculate_berm_design
from explosions_core.calc.lightning_protection import (
    calculate_lightning_protection,
    generate_storage_checkpoints_3d,
    single_rod_zone,
)
from explosions_core.domain import (
    BermDesignInput,
    BermSoilMaterial,
    LightningArresterMast,
    LightningZoneType,
)


def _berm_input(**overrides) -> BermDesignInput:
    values = {
        "storage_length_m": 20.0,
        "storage_width_m": 10.0,
        "load_top_height_m": 2.5,
        "crest_width_m": 1.5,
        "soil_material": BermSoilMaterial.PLASTIC_CLAY_LOAM,
        "natural_slope_angle_deg": 45.0,
    }
    values.update(overrides)
    return BermDesignInput(**values)


def _mast(height_m: float) -> LightningArresterMast:
    return LightningArresterMast(mast_id="M1", x_m=0.0, y_m=10.0, height_h_m=height_m)


def _codes(violations) -> list[str]:
    return [violation.code for violation in violations]


def test_stone_or_gravel_is_rejected_by_clause_603():
    result = calculate_berm_design(_berm_input(soil_material=BermSoilMaterial.STONE_OR_GRAVEL))

    assert "BERM_INVALID_SOIL_MATERIAL" in _codes(result.violations)
    violation = next(v for v in result.violations if v.code == "BERM_INVALID_SOIL_MATERIAL")
    assert "п. 603 Приказа МИР РК № 343" in violation.clause


def test_combustible_material_is_rejected_by_clause_603():
    result = calculate_berm_design(_berm_input(soil_material=BermSoilMaterial.COMBUSTIBLE_MATERIAL))

    assert "BERM_INVALID_SOIL_MATERIAL" in _codes(result.violations)


def test_permitted_soils_produce_no_soil_violation():
    for soil in (BermSoilMaterial.PLASTIC_CLAY_LOAM, BermSoilMaterial.SANDY_FREE_FLOWING):
        result = calculate_berm_design(_berm_input(soil_material=soil))

        assert "BERM_INVALID_SOIL_MATERIAL" not in _codes(result.violations)


def test_trapezoidal_berm_geometry_at_45_degrees():
    result = calculate_berm_design(_berm_input())

    assert result.berm_height_m == pytest.approx(4.0)
    assert result.base_width_m == pytest.approx(9.5)
    assert result.cross_section_area_m2 == pytest.approx(22.0)


def test_berm_lengths_volume_and_footprint():
    result = calculate_berm_design(_berm_input())

    assert result.main_berm_centerline_length_m == pytest.approx(105.5)
    assert result.screen_berm_length_m == pytest.approx(8.5)
    assert result.total_earthwork_volume_m3 == pytest.approx(22.0 * (105.5 + 8.5))
    assert result.outer_footprint_length_m == pytest.approx(42.0)
    assert result.outer_footprint_width_m == pytest.approx(32.0)
    assert result.violations == []


def test_crest_narrower_than_1_m_is_a_violation_of_clause_604():
    assert _codes(calculate_berm_design(_berm_input(crest_width_m=1.0)).violations) == []
    result = calculate_berm_design(_berm_input(crest_width_m=0.9))

    assert "BERM_CREST_WIDTH_TOO_SMALL" in _codes(result.violations)


def test_toe_clearance_is_not_regulated_by_clauses_602_605():
    result = calculate_berm_design(_berm_input(wall_to_inner_toe_clearance_m=0.5))

    assert result.violations == []


def test_crest_less_than_1_5_m_above_load_is_a_violation_of_clause_604():
    result = calculate_berm_design(_berm_input(crest_elevation_above_load_m=1.4))

    assert "BERM_CREST_TOO_LOW" in _codes(result.violations)
    assert result.berm_height_m == pytest.approx(3.9)


def test_zone_a_reference_values_for_14_5_m_mast_at_6_5_m():
    h0, r0, rx = single_rod_zone(14.5, 6.5, LightningZoneType.ZONE_A)

    assert h0 == pytest.approx(12.325)
    assert r0 == pytest.approx(15.5295, abs=1e-4)
    assert rx == pytest.approx(7.3396, abs=1e-4)


def test_zone_b_reference_values_for_14_5_m_mast_at_6_5_m():
    h0, r0, rx = single_rod_zone(14.5, 6.5, LightningZoneType.ZONE_B)

    assert h0 == pytest.approx(13.34)
    assert r0 == pytest.approx(21.75)
    assert rx == pytest.approx(1.5 * (14.5 - 6.5 / 0.92))


def test_point_above_zone_top_is_not_protected():
    _, _, rx = single_rod_zone(10.0, 9.0, LightningZoneType.ZONE_A)

    assert rx == 0.0


def test_checkpoints_use_default_vent_height_above_ridge():
    points = generate_storage_checkpoints_3d(12.0, 9.0, 6.0, 7.5)
    vent = next(p for p in points if p.name == "Верх дефлектора вентшахты")

    assert vent.z_height_m == pytest.approx(8.3)
    assert len(points) == 7


def test_mast_closer_than_5_m_to_storage_walls_is_a_violation():
    mast = LightningArresterMast(mast_id="M1", x_m=0.0, y_m=0.0, height_h_m=20.0)
    result = calculate_lightning_protection([mast], LightningZoneType.ZONE_A, 12.0, 9.0, 6.0, 7.5)

    assert "LIGHTNING_MAST_TOO_CLOSE_TO_STORAGE" in _codes(result.violations)
    assert result.is_fully_protected is False


def test_low_mast_leaves_roof_points_outside_zone_a():
    result = calculate_lightning_protection([_mast(8.0)], LightningZoneType.ZONE_A, 12.0, 9.0, 6.0, 7.5)

    assert result.is_fully_protected is False
    assert "Торец конька (восток)" in result.unprotected_points
    assert "Верх дефлектора вентшахты" in result.unprotected_points
    assert result.violations == []


def test_auto_selected_mast_height_covers_all_points():
    base = calculate_lightning_protection([_mast(8.0)], LightningZoneType.ZONE_A, 12.0, 9.0, 6.0, 7.5)
    required = base.min_recommended_mast_height_m

    assert required is not None
    assert required == pytest.approx(22.0, abs=0.1)

    covered = calculate_lightning_protection([_mast(required)], LightningZoneType.ZONE_A, 12.0, 9.0, 6.0, 7.5)
    assert covered.is_fully_protected is True
    assert covered.unprotected_points == []

    short = calculate_lightning_protection([_mast(required - 0.2)], LightningZoneType.ZONE_A, 12.0, 9.0, 6.0, 7.5)
    assert short.is_fully_protected is False


def test_mast_results_contain_required_fields():
    result = calculate_lightning_protection([_mast(14.5)], LightningZoneType.ZONE_A, 12.0, 9.0, 6.0, 7.5)

    assert len(result.mast_results) == 1
    entry = result.mast_results[0]
    assert {"h0_m", "r0_ground_m", "rx_at_eaves_m", "rx_at_ridge_m"} <= set(entry)
