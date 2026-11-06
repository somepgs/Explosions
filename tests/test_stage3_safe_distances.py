"""Этап 3: безопасные расстояния по УВВ (п. 10, таблица 2) и по передаче детонации (п. 15–19, таблицы 4, 5)
Приложения 11 Приказа № 343 (ред. от 02.10.2025)."""

import math

import pytest

from explosions_core.calc.safe_distances import (
    FORMULA_10,
    FORMULA_11,
    SafeDistanceEngine,
    axial_min_distance,
    calculate_clear_distance,
    calculate_detonation_distance,
    calculate_detonation_distance_pair,
    calculate_explosive_mass,
    calculate_tnt_equivalent_mass,
    calculate_uvv_safe_distance,
    detonation_charge_placement,
    get_kd,
    load_appendix11_tables,
    table_5_distance,
    uvv_charge_placement,
    uvv_coefficient_and_formula,
)
from explosions_core.domain import (
    ChargePlacementType,
    CompatibilityGroup,
    DetonationFormulaType,
    DetonationMaterialClass,
    ExplosiveItem,
    ExternalProtectedObject,
    LocationType,
    StorageBuilding,
    WarehouseCategory,
    WarehouseDuration,
)

AN = DetonationMaterialClass.AN_BASED
TNT = DetonationMaterialClass.TNT
DET = DetonationMaterialClass.DETONATORS
OPEN = ChargePlacementType.OPEN_SURFACE
BURIED = ChargePlacementType.BURIED_OWN_HEIGHT


def make_storage(
    storage_id: str,
    mass_kg: float,
    detonation_class: DetonationMaterialClass = AN,
    *,
    is_bermed: bool = False,
    location: LocationType = LocationType.SURFACE,
    x_m: float = 0.0,
    y_m: float = 0.0,
    length_m: float = 10.0,
    width_m: float = 10.0,
    stack_width_b_m: float | None = None,
    tnt_coeff: float | None = None,
) -> StorageBuilding:
    return StorageBuilding(
        name=f"Хранилище {storage_id}",
        storage_id=storage_id,
        category=WarehouseCategory.BASIS,
        duration=WarehouseDuration.PERMANENT,
        location_type=location,
        is_bermed=is_bermed,
        items=[
            ExplosiveItem(
                name=f"ВВ {storage_id}",
                group=CompatibilityGroup.D,
                mass_kg=mass_kg,
                detonation_class=detonation_class,
                tnt_equivalent_coeff=tnt_coeff,
            )
        ],
        x_m=x_m,
        y_m=y_m,
        length_m=length_m,
        width_m=width_m,
        stack_width_b_m=stack_width_b_m,
    )


def make_object(degree: int, distance: float = 1000.0, **kwargs) -> ExternalProtectedObject:
    return ExternalProtectedObject(
        object_id=f"OBJ{degree}",
        name=f"Объект степени {degree}",
        allowed_damage_degree=degree,
        actual_distance_m=distance,
        **kwargs,
    )


# УВВ: формулы (10), (11) и таблица 2

def test_open_charge_up_to_10_t_uses_formula_11_with_table_2_maximum():
    formula, coeff, kv_range = uvv_coefficient_and_formula(2, OPEN, 9000.0, load_appendix11_tables())
    assert formula == FORMULA_11
    assert kv_range == (10.0, 30.0)
    assert coeff == 30.0


def test_open_charge_exactly_10_t_still_uses_formula_11():
    formula, _, _ = uvv_coefficient_and_formula(1, OPEN, 10000.0, load_appendix11_tables())
    assert formula == FORMULA_11


def test_open_charge_above_10_t_uses_formula_10():
    result = calculate_uvv_safe_distance("S", make_object(2), 27000.0, OPEN)
    assert result.formula_used == FORMULA_10
    assert result.applied_coeff == 100.0
    assert result.required_distance_m == pytest.approx(100.0 * 30.0)


def test_buried_charge_switches_to_formula_10_only_above_20_t():
    tables = load_appendix11_tables()
    assert uvv_coefficient_and_formula(1, BURIED, 15000.0, tables)[0] == FORMULA_11
    formula, coeff, _ = uvv_coefficient_and_formula(1, BURIED, 27000.0, tables)
    assert (formula, coeff) == (FORMULA_10, 200.0)


@pytest.mark.parametrize(("degree", "placement", "k_max"), [(3, BURIED, 4.0), (4, OPEN, 4.0), (4, BURIED, 2.0), (5, OPEN, 2.0), (5, BURIED, 1.0)])
def test_degrees_without_k_v_large_mass_always_use_formula_11(degree, placement, k_max):
    formula, coeff, _ = uvv_coefficient_and_formula(degree, placement, 500000.0, load_appendix11_tables())
    assert formula == FORMULA_11
    assert coeff == k_max


def test_formula_11_substitution_900_kg():
    result = calculate_uvv_safe_distance("S", make_object(4), 900.0, OPEN)
    assert result.required_distance_m == pytest.approx(4.0 * 30.0)


def test_custom_coefficient_and_topography_reduction():
    obj = make_object(2, custom_kv_override=60.0, topography_reduction_coeff=0.5)
    result = calculate_uvv_safe_distance("S", obj, 27000.0, OPEN)
    assert result.required_distance_m == pytest.approx(60.0 * 30.0 * 0.5)


def test_uvv_violation_cites_appendix_11():
    result = calculate_uvv_safe_distance("S", make_object(4, distance=100.0), 900.0, OPEN)
    assert not result.is_safe
    assert result.violations[0].code == "UVV_SAFE_DISTANCE"
    assert "п. 10" in result.violations[0].clause and "Приложения 11" in result.violations[0].clause


def test_bermed_storage_is_open_for_degrees_1_2_and_buried_above():
    storage = make_storage("B", 1000.0, is_bermed=True)
    assert uvv_charge_placement(storage, 1) == OPEN
    assert uvv_charge_placement(storage, 2) == OPEN
    assert uvv_charge_placement(storage, 3) == BURIED
    assert uvv_charge_placement(make_storage("U", 1000.0), 3) == OPEN
    assert uvv_charge_placement(make_storage("G", 1000.0, location=LocationType.BURIED), 1) == BURIED


def test_underground_storage_is_rejected():
    with pytest.raises(ValueError):
        uvv_charge_placement(make_storage("P", 1000.0, location=LocationType.UNDERGROUND), 1)


# Передача детонации: формула (19), таблицы 4, 5

def test_formula_19_uses_fourth_root_of_passive_width():
    assert calculate_detonation_distance(16000.0, 0.8, 1.6) == pytest.approx(0.8 * 16000 ** (1 / 3) * 1.6 ** 0.25)


def test_bermed_storage_is_buried_for_detonation_transfer():
    assert detonation_charge_placement(make_storage("B", 1.0, is_bermed=True)) == BURIED
    assert detonation_charge_placement(make_storage("U", 1.0)) == OPEN


def test_kd_for_mixed_passive_charge_takes_most_sensitive_material():
    tables = load_appendix11_tables()
    k_d = get_kd({AN: 1000.0}, OPEN, {AN: 900.0, TNT: 100.0}, OPEN, tables)
    assert k_d == 1.3


def test_asymmetric_pair_takes_maximum_of_both_directions():
    s1 = make_storage("S1", 40000.0, TNT, is_bermed=True, x_m=0.0)
    s2 = make_storage("S2", 5000.0, AN, x_m=200.0)
    pair = calculate_detonation_distance_pair(s1, s2, formula=DetonationFormulaType.FORMULA_19)
    assert pair.k_d_i_to_j == 1.0
    assert pair.k_d_j_to_i == 1.0
    assert pair.r_d_i_to_j_m != pytest.approx(pair.r_d_j_to_i_m)
    assert pair.governing_required_r_d_m == max(pair.r_d_i_to_j_m, pair.r_d_j_to_i_m)


def test_pair_violation_cites_clause_15():
    s1 = make_storage("S1", 420000.0, AN, x_m=0.0)
    s2 = make_storage("S2", 40000.0, TNT, is_bermed=True, x_m=10.0 + 35.0, y_m=50.0)
    pair = calculate_detonation_distance_pair(s1, s2)
    assert not pair.is_safe
    assert pair.violations[0].code == "DETONATION_TRANSFER_DISTANCE"
    assert "п. 15" in pair.violations[0].clause and "Приложения 11" in pair.violations[0].clause


def test_table_5_interpolation_and_out_of_range():
    tables = load_appendix11_tables()
    assert table_5_distance({AN: 1.0}, OPEN, {AN: 1.0}, OPEN, 17500.0, 1.6, tables) == pytest.approx(23.5)
    assert table_5_distance({AN: 1.0}, OPEN, {AN: 1.0}, OPEN, 5000.0, 1.6, tables) is None
    assert table_5_distance({AN: 1.0}, OPEN, {AN: 1.0}, OPEN, 17500.0, 2.0, tables) is None


def test_max_conservative_not_less_than_formula_19():
    s1 = make_storage("S1", 60000.0, AN, x_m=0.0)
    s2 = make_storage("S2", 60000.0, AN, x_m=100.0)
    formula = calculate_detonation_distance_pair(s1, s2, formula=DetonationFormulaType.FORMULA_19)
    conservative = calculate_detonation_distance_pair(s1, s2)
    assert conservative.governing_required_r_d_m >= formula.governing_required_r_d_m


def test_table_5_mode_requires_applicable_table():
    s1 = make_storage("S1", 5000.0, AN, x_m=0.0)
    s2 = make_storage("S2", 5000.0, AN, x_m=100.0)
    with pytest.raises(ValueError):
        calculate_detonation_distance_pair(s1, s2, formula=DetonationFormulaType.TABLE_5)


def test_axial_rule_for_elongated_storages_on_one_axis():
    s1 = make_storage("S1", 100.0, AN, x_m=0.0, length_m=30.0, width_m=12.0)
    s2 = make_storage("S2", 100.0, AN, x_m=40.0, length_m=30.0, width_m=9.0)
    assert axial_min_distance(s1, s2) == pytest.approx(24.0)
    pair = calculate_detonation_distance_pair(s1, s2)
    assert pair.governing_required_r_d_m == pytest.approx(24.0)
    assert not pair.is_safe
    side_by_side = make_storage("S3", 100.0, AN, x_m=0.0, y_m=40.0, length_m=30.0, width_m=12.0)
    assert axial_min_distance(s1, side_by_side) is None


def test_missing_detonation_class_raises_value_error():
    s1 = make_storage("S1", 100.0, x_m=0.0)
    s1.items[0] = s1.items[0].model_copy(update={"detonation_class": None})
    with pytest.raises(ValueError):
        calculate_detonation_distance_pair(s1, make_storage("S2", 100.0, x_m=50.0))


# Вспомогательные функции и движок

def test_masses_and_clear_distance():
    s1 = make_storage("S1", 1000.0, tnt_coeff=0.8, x_m=0.0)
    s2 = make_storage("S2", 1000.0, x_m=13.0, y_m=14.0)
    assert calculate_explosive_mass(s1.items) == 1000.0
    assert calculate_tnt_equivalent_mass(s1.items) == pytest.approx(800.0)
    assert calculate_clear_distance(s1, s2) == pytest.approx(math.hypot(3.0, 4.0))


def test_engine_matrices():
    storages = [make_storage(f"S{i}", 1000.0, x_m=40.0 * i) for i in range(3)]
    engine = SafeDistanceEngine()
    assert len(engine.detonation_matrix(storages)) == 3
    uvv = engine.uvv_matrix(storages, [make_object(4)])
    assert len(uvv) == 3
    assert all(result.placement == OPEN for result in uvv)
