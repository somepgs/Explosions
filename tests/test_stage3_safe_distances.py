import math
from pathlib import Path

import pytest

from explosions_core.norms.constants_rk343 import DEFAULT_STACK_WIDTH_B_M
from explosions_core.calc.safe_distances import (
    SafeDistanceEngine,
    calculate_clear_distance,
    calculate_detonation_distance,
    calculate_detonation_distance_pair,
    calculate_tnt_equivalent_mass,
    calculate_uvv_safe_distance,
    interpolate_from_normative_table,
    load_appendix11_tables,
    select_detonation_profile,
)
from explosions_core.domain import (
    ChargePlacementType,
    CompatibilityGroup,
    DetonationFormulaType,
    ExplosiveItem,
    ExternalProtectedObject,
    LocationType,
    StorageBuilding,
    WarehouseCategory,
    WarehouseDuration,
)

TABLES_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "explosions_core" / "norms" / "data" / "appendix11_tables_rk343.json"
)


def _storage(
    name: str,
    mass_kg: float,
    *,
    is_bermed: bool = False,
    x: float = 0.0,
    y: float = 0.0,
    location: LocationType = LocationType.SURFACE,
    b: float | None = None,
) -> StorageBuilding:
    return StorageBuilding(
        name=name,
        category=WarehouseCategory.BASIS,
        duration=WarehouseDuration.PERMANENT,
        location_type=location,
        is_bermed=is_bermed,
        stack_width_b_m=b,
        x_m=x,
        y_m=y,
        length_m=10.0,
        width_m=10.0,
        items=[
            ExplosiveItem(
                name="ВВ",
                group=CompatibilityGroup.D,
                mass_kg=mass_kg,
                tnt_equivalent_coeff=1.0,
            )
        ],
    )


def _object(
    degree: int = 1,
    distance: float = 1000.0,
    override: float | None = None,
    topography: float = 1.0,
) -> ExternalProtectedObject:
    return ExternalProtectedObject(
        object_id="OBJ-1",
        name="Жилой дом",
        allowed_damage_degree=degree,
        custom_kv_override=override,
        actual_distance_m=distance,
        topography_reduction_coeff=topography,
    )


def test_tnt_equivalent_mass_sums_items_with_coefficients():
    items = [
        ExplosiveItem(name="А", group=CompatibilityGroup.D, mass_kg=1000.0, tnt_equivalent_coeff=1.0),
        ExplosiveItem(name="Б", group=CompatibilityGroup.S, mass_kg=500.0, tnt_equivalent_coeff=0.5),
    ]

    assert calculate_tnt_equivalent_mass(items) == pytest.approx(1250.0)


def test_tnt_equivalent_mass_requires_coefficient():
    items = [ExplosiveItem(name="Б", group=CompatibilityGroup.S, mass_kg=500.0)]

    with pytest.raises(ValueError):
        calculate_tnt_equivalent_mass(items)


def test_uvv_square_root_formula_below_1000_kg():
    result = calculate_uvv_safe_distance("S1", _object(override=2.0), 900.0)

    assert "Q <= 1000" in result.formula_used
    assert result.required_distance_m == pytest.approx(2.0 * 30.0)


def test_uvv_cube_root_formula_above_1000_kg():
    result = calculate_uvv_safe_distance("S1", _object(override=2.0), 27000.0)

    assert "Q > 1000" in result.formula_used
    assert result.required_distance_m == pytest.approx(2.0 * 30.0)


def test_uvv_default_coefficient_uses_table_maximum():
    result = calculate_uvv_safe_distance("S1", _object(degree=1), 27000.0)

    assert result.applied_coeff_kv == pytest.approx(150.0)
    assert result.required_distance_m == pytest.approx(150.0 * 30.0)


def test_uvv_topography_reduction_applies():
    result = calculate_uvv_safe_distance("S1", _object(override=2.0, topography=0.5), 900.0)

    assert result.required_distance_m == pytest.approx(30.0)


def test_uvv_violation_when_distance_is_too_small():
    result = calculate_uvv_safe_distance("S1", _object(degree=1, distance=1000.0), 27000.0)

    assert result.is_safe is False
    assert result.violations[0].code == "UVV_SAFE_DISTANCE"
    assert "Глава 3" in result.violations[0].clause


def test_uvv_no_violation_when_distance_is_enough():
    result = calculate_uvv_safe_distance("S1", _object(degree=1, distance=5000.0), 27000.0)

    assert result.is_safe is True
    assert result.violations == []


def test_uvv_missing_coefficient_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        calculate_uvv_safe_distance("S1", _object(degree=4, distance=1000.0), 500.0)


def test_detonation_formula_19_stack_width_gives_80_m():
    r_d = calculate_detonation_distance(16000.0, 0.8, 1.6, DetonationFormulaType.FORMULA_19_STACK_WIDTH)

    assert r_d == pytest.approx(0.8 * math.sqrt(16000.0 / 1.6))
    assert r_d == pytest.approx(80.0)


def test_detonation_formula_18_cubic_root():
    r_d = calculate_detonation_distance(27000.0, 0.8, 1.6, DetonationFormulaType.FORMULA_18_CUBIC)

    assert r_d == pytest.approx(0.8 * 30.0)


def test_detonation_max_conservative_takes_larger_formula():
    r_d = calculate_detonation_distance(16000.0, 0.8, 1.6, DetonationFormulaType.MAX_CONSERVATIVE)

    assert r_d == pytest.approx(80.0)


def test_detonation_pair_is_asymmetric_and_uses_maximum():
    storage_1 = _storage("S1", 40000.0, is_bermed=True, x=0.0, b=DEFAULT_STACK_WIDTH_B_M)
    storage_2 = _storage("S2", 5000.0, is_bermed=False, x=300.0)

    result = calculate_detonation_distance_pair(storage_1, storage_2)

    expected_1_to_2 = 1.2 * math.sqrt(40000.0 / 1.6)
    expected_2_to_1 = 1.0 * math.sqrt(5000.0 / 1.6)
    assert result.r_d_i_to_j_m == pytest.approx(expected_1_to_2)
    assert result.r_d_j_to_i_m == pytest.approx(expected_2_to_1)
    assert result.r_d_i_to_j_m != pytest.approx(result.r_d_j_to_i_m)
    assert result.governing_required_r_d_m == pytest.approx(max(expected_1_to_2, expected_2_to_1))
    assert result.is_safe is True


def test_detonation_violation_when_storages_are_too_close():
    storage_1 = _storage("S1", 16000.0, is_bermed=True, x=0.0)
    storage_2 = _storage("S2", 16000.0, is_bermed=True, x=45.0)

    result = calculate_detonation_distance_pair(storage_1, storage_2)

    assert result.actual_clear_distance_m == pytest.approx(35.0)
    assert result.governing_required_r_d_m == pytest.approx(80.0)
    assert result.is_safe is False
    assert result.violations[0].code == "DETONATION_TRANSFER_DISTANCE"
    assert "п. 15" in result.violations[0].clause
    assert "Приложения 11" in result.violations[0].clause


def test_detonation_no_violation_when_storages_are_far_enough():
    storage_1 = _storage("S1", 16000.0, is_bermed=True, x=0.0)
    storage_2 = _storage("S2", 16000.0, is_bermed=True, x=100.0)

    result = calculate_detonation_distance_pair(storage_1, storage_2)

    assert result.is_safe is True
    assert result.violations == []


@pytest.mark.parametrize(
    ("active_bermed", "passive_bermed", "high_sensitivity", "granular", "expected"),
    [
        (False, False, True, False, "UNBERMED_TO_UNBERMED_HIGH_SENS"),
        (False, False, False, False, "UNBERMED_TO_UNBERMED_STANDARD"),
        (False, True, False, False, "UNBERMED_TO_BERMED"),
        (True, False, False, False, "BERMED_TO_UNBERMED"),
        (True, True, False, False, "BERMED_TO_BERMED_STANDARD"),
        (True, True, False, True, "BERMED_TO_BERMED_GRANULAR"),
    ],
)
def test_select_detonation_profile(active_bermed, passive_bermed, high_sensitivity, granular, expected):
    active = _storage("A", 1000.0, is_bermed=active_bermed)
    passive = _storage("P", 1000.0, is_bermed=passive_bermed)

    profile = select_detonation_profile(
        active, passive, high_sensitivity=high_sensitivity, granular_asvv=granular
    )

    assert profile == expected


def test_select_detonation_profile_buried_pair():
    active = _storage("A", 1000.0, location=LocationType.BURIED)
    passive = _storage("P", 1000.0, location=LocationType.BURIED)

    assert select_detonation_profile(active, passive) == "BURIED_TO_BURIED"


def test_clear_distance_is_diagonal_between_rectangles():
    storage_1 = _storage("S1", 1000.0, x=0.0, y=0.0)
    storage_2 = _storage("S2", 1000.0, x=13.0, y=14.0)

    assert calculate_clear_distance(storage_1, storage_2) == pytest.approx(5.0)


def test_interpolate_linear_between_nodes():
    grid = [
        {"mass_kg": 1000.0, "distance_m": 100.0},
        {"mass_kg": 3000.0, "distance_m": 200.0},
    ]

    assert interpolate_from_normative_table(2000.0, grid) == pytest.approx(150.0)
    assert interpolate_from_normative_table(3000.0, grid) == pytest.approx(200.0)


def test_interpolate_outside_grid_raises():
    grid = [
        {"mass_kg": 1000.0, "distance_m": 100.0},
        {"mass_kg": 3000.0, "distance_m": 200.0},
    ]

    with pytest.raises(ValueError):
        interpolate_from_normative_table(5000.0, grid)


def test_interpolate_empty_grid_raises():
    with pytest.raises(ValueError):
        interpolate_from_normative_table(1000.0, [])


def test_json_tables_load_with_expected_coefficients():
    tables = load_appendix11_tables(TABLES_PATH)

    assert tables["detonation_coefficients_kd"]["DEFAULT_STACK_WIDTH_B_M"] == pytest.approx(DEFAULT_STACK_WIDTH_B_M)
    assert tables["detonation_coefficients_kd"]["profiles"]["BERMED_TO_BERMED_STANDARD"] == pytest.approx(0.8)
    assert tables["uvv_damage_degrees"]["1"]["open_surface"]["k_v"] == pytest.approx(5.0)
    assert tables["tabular_lookup_grids"] == []


def test_engine_uvv_uses_storage_tnt_mass():
    storage = _storage("S1", 27000.0)

    result = SafeDistanceEngine().uvv(storage, _object(degree=1, distance=1000.0))

    assert result.equivalent_tnt_mass_kg == pytest.approx(27000.0)
    assert result.required_distance_m == pytest.approx(150.0 * 30.0)
    assert result.is_safe is False
    assert result.violations[0].code == "UVV_SAFE_DISTANCE"
