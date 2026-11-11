"""Задание № 9: эталонные (golden) проверки по тексту Приказа МИР РК № 343 (ред. от 02.10.2025).

Источник — Documentation/v1400010244.02-10-2025.rus.pdf: примеры п. 21 Приложения 11, таблицы 4 и 5,
п. 604–605 и реестр источников констант.
"""

import pytest

from explosions_core.calc.berm_calculator import calculate_berm_design, screen_required_crest_length
from explosions_core.calc.safe_distances import (
    calculate_detonation_distance,
    calculate_detonation_distance_pair,
    load_appendix11_tables,
)
from explosions_core.domain import (
    BermDesignInput,
    BermSoilMaterial,
    CompatibilityGroup,
    DetonationFormulaType,
    DetonationMaterialClass,
    ExplosiveItem,
    LocationType,
    StorageBuilding,
    WarehouseCategory,
    WarehouseDuration,
)
from explosions_core.norms import constants_rk343
from explosions_core.norms.constants_rk343 import (
    DEFAULT_STACK_WIDTH_B_M,
    UVV_FORMULA_MASS_BURIED_THRESHOLD_KG,
    UVV_FORMULA_MASS_OPEN_THRESHOLD_KG,
)
from explosions_core.norms.sources import CONSTANT_SOURCES, DESIGN_DEFAULT, VERIFIED, constants_with_status

B = DEFAULT_STACK_WIDTH_B_M
DETONATOR_EXPLOSIVE_MASS_KG = 0.0015  # масса ВВ в одном ЭД, пример 2 п. 21 Приложения 11


def storage(storage_id: str, mass_kg: float, cls: DetonationMaterialClass, *, bermed: bool, x_m: float) -> StorageBuilding:
    return StorageBuilding(
        name=storage_id,
        storage_id=storage_id,
        category=WarehouseCategory.BASIS,
        duration=WarehouseDuration.PERMANENT,
        location_type=LocationType.SURFACE,
        is_bermed=bermed,
        items=[ExplosiveItem(name=storage_id, group=CompatibilityGroup.D, mass_kg=mass_kg, detonation_class=cls)],
        x_m=x_m,
        y_m=0.0,
        length_m=10.0,
        width_m=10.0,
    )


def test_example_1_bermed_tnt_120_t_and_open_granulite_240_t():
    """Пример 1 п. 21: K_д = 1 в обе стороны, b = 1,6 м, r_д = 69,9 м."""
    tnt = storage("TNT", 120000.0, DetonationMaterialClass.TNT, bermed=True, x_m=0.0)
    granulite = storage("GR", 240000.0, DetonationMaterialClass.AN_BASED, bermed=False, x_m=100.0)
    pair = calculate_detonation_distance_pair(tnt, granulite, formula=DetonationFormulaType.FORMULA_19)
    assert pair.k_d_i_to_j == 1.0 and pair.k_d_j_to_i == 1.0
    assert round(pair.governing_required_r_d_m, 1) == 69.9


def test_example_2_detonators_active_to_open_tnt():
    """Пример 2 п. 21: 500 000 ЭД по 0,0015 кг = 750 кг ВВ, K_д = 0,7 (детонаторы открытые -> тротил открытый)."""
    q_detonators = 500000 * DETONATOR_EXPLOSIVE_MASS_KG
    assert q_detonators == pytest.approx(750.0)
    detonators = storage("ED", q_detonators, DetonationMaterialClass.DETONATORS, bermed=False, x_m=0.0)
    tnt = storage("TNT", 120000.0, DetonationMaterialClass.TNT, bermed=False, x_m=100.0)
    pair = calculate_detonation_distance_pair(detonators, tnt, formula=DetonationFormulaType.FORMULA_19)
    assert pair.k_d_i_to_j == 0.7
    assert pair.r_d_i_to_j_m == pytest.approx(0.7 * 750 ** (1 / 3) * B ** 0.25)


def test_example_3_grammonite_420_t_and_bermed_tnt_40_t():
    """Пример 3 п. 21: 84,2 м (граммонит активный) и 38,5 м (тротил активный), K_д = 1."""
    grammonite = storage("GM", 420000.0, DetonationMaterialClass.AN_BASED, bermed=False, x_m=0.0)
    tnt = storage("TNT", 40000.0, DetonationMaterialClass.TNT, bermed=True, x_m=55.0)
    pair = calculate_detonation_distance_pair(grammonite, tnt, formula=DetonationFormulaType.FORMULA_19)
    assert round(pair.r_d_i_to_j_m, 1) == 84.2
    assert round(pair.r_d_j_to_i_m, 1) == 38.5
    assert pair.actual_clear_distance_m == pytest.approx(45.0)
    assert not pair.is_safe


def _table_5_rows():
    return load_appendix11_tables()["table_5_rd_b_1_6_m"]


@pytest.mark.parametrize("row", _table_5_rows(), ids=lambda row: f"{row['active']}->{row['passive']}")
def test_table_5_matches_formula_19_within_rounding(row):
    """Таблица 5 рассчитана по формуле (19) при b = 1,6 м: расхождение не более 1 м (округление в таблице)."""
    for mass_t, distance in row["distances_m"].items():
        assert abs(calculate_detonation_distance(float(mass_t) * 1000.0, row["k_d"], B) - distance) <= 1.0


@pytest.mark.parametrize("row", _table_5_rows(), ids=lambda row: f"{row['active']}->{row['passive']}")
def test_table_5_kd_matches_table_4(row):
    assert load_appendix11_tables()["table_4_kd"][row["active"]][row["passive"]] == row["k_d"]


def test_table_4_is_complete_8_by_8():
    table = load_appendix11_tables()["table_4_kd"]
    assert len(table) == 8
    assert all(len(row) == 8 for row in table.values())


def test_table_2_thresholds_match_constants():
    table = load_appendix11_tables()["table_2_uvv"]
    for degree in ("1", "2", "3"):
        assert table[degree]["open"]["formula_10_above_t"] * 1000.0 == UVV_FORMULA_MASS_OPEN_THRESHOLD_KG
    for degree in ("1", "2"):
        assert table[degree]["buried"]["formula_10_above_t"] * 1000.0 == UVV_FORMULA_MASS_BURIED_THRESHOLD_KG
    for degree, placement in (("3", "buried"), ("4", "open"), ("4", "buried"), ("5", "open"), ("5", "buried")):
        assert table[degree][placement]["formula_10_above_t"] is None


def _berm(**overrides) -> BermDesignInput:
    base = {
        "storage_length_m": 12.0,
        "storage_width_m": 8.0,
        "load_top_height_m": 2.0,
        "soil_material": BermSoilMaterial.PLASTIC_CLAY_LOAM,
        "natural_slope_angle_deg": 45.0,
    }
    base.update(overrides)
    return BermDesignInput(**base)


def test_clause_604_crest_1_5_m_above_load_and_width_1_m():
    result = calculate_berm_design(_berm())
    assert result.berm_height_m == pytest.approx(3.5)
    assert result.crest_width_m == 1.0
    assert result.violations == []
    low = calculate_berm_design(_berm(crest_elevation_above_load_m=1.0, crest_width_m=0.8))
    codes = {violation.code for violation in low.violations}
    assert codes == {"BERM_CREST_TOO_LOW", "BERM_CREST_WIDTH_TOO_SMALL"}
    assert all("п. 604" in violation.clause for violation in low.violations)


def test_clause_605_screen_sight_line():
    data = _berm(storage_width_m=20.0, entrance_opening_width_m=4.0, screen_overlap_each_side_m=0.5)
    result = calculate_berm_design(data)
    required = screen_required_crest_length(data, result.base_width_m)
    assert result.screen_required_length_m == pytest.approx(required)
    assert required > result.screen_berm_length_m
    assert [violation.code for violation in result.violations] == ["BERM_SCREEN_TOO_SHORT"]
    assert "п. 605" in result.violations[0].clause
    long_enough = calculate_berm_design(data.model_copy(update={"screen_overlap_each_side_m": required}))
    assert long_enough.violations == []


def test_every_constant_has_registered_source():
    names = {name for name in dir(constants_rk343) if name.isupper()}
    assert names == set(CONSTANT_SOURCES)


RD_ZONE_CONSTANTS = ("ZONE_A_H0_COEFF", "ZONE_A_R0_BASE", "ZONE_A_R0_SLOPE", "ZONE_B_H0_COEFF", "ZONE_B_R0_COEFF")


def test_lightning_constants_verification_status():
    verified = constants_with_status(VERIFIED)
    for name in RD_ZONE_CONSTANTS:
        assert name in verified
        assert "РД 34.21.122-87, Приложение 3, п. 1.1" in CONSTANT_SOURCES[name][0]
    design_defaults = constants_with_status(DESIGN_DEFAULT)
    assert "MIN_ARRESTER_CLEARANCE_FROM_STORAGE_WALL_M" in design_defaults
    assert "MIN_GROUNDING_DIST_FROM_ENTRANCE_M" in design_defaults
    assert "MIN_FENCE_HEIGHT_PERMANENT_M" in verified


def test_rd_zone_constants_match_appendix_3_clause_1_1():
    assert constants_rk343.ZONE_A_H0_COEFF == 0.85
    assert (constants_rk343.ZONE_A_R0_BASE, constants_rk343.ZONE_A_R0_SLOPE) == (1.1, 0.002)
    assert constants_rk343.ZONE_B_H0_COEFF == 0.92
    assert constants_rk343.ZONE_B_R0_COEFF == 1.5
