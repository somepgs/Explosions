"""Задание № 10: сверка с СП РК 2.04-103-2013, СО 153-34.21.122-2003, таблицей 3 Приложения 11 и ТР ТС 028/2012."""

import math

import pytest

from explosions_core.calc.lightning_protection import (
    all_points_covered,
    calculate_lightning_protection,
    generate_storage_checkpoints_3d,
    rolling_sphere_radius,
    so153_cone_parameters,
    so153_single_rod_zone,
    solve_common_arrester_height,
)
from explosions_core.calc.safe_distances import (
    SafeDistanceEngine,
    load_appendix11_tables,
    table3_charge_placement,
    table3_uvv_distance,
)
from explosions_core.domain import (
    ChargePlacementType,
    CompatibilityGroup,
    ExplosiveItem,
    ExternalProtectedObject,
    LightningArresterMast,
    LightningMethod,
    LightningProtectionLevel,
    LightningReliability,
    LightningSpec,
    LightningZoneType,
    LocationType,
    StorageBuilding,
    UVVMethod,
    WarehouseCategory,
    WarehouseDuration,
)
from explosions_core.pipeline import calculate_project
from explosions_core.validators.compatibility import check_classification_codes
from tests.fixtures.sample_project import build_sample_project_definition

TABLE3_KNOWN_ROUNDING_CELLS = {
    ("1", "buried", 500),
    ("1", "buried", 1000),
    ("1", "buried", 2000),
    ("1", "open", 1000),
    ("2", "buried", 1000),
    ("2", "open", 500),
}


def _storage(
    *,
    duration: WarehouseDuration = WarehouseDuration.PERMANENT,
    location: LocationType = LocationType.SURFACE,
    is_bermed: bool = False,
    items: list[ExplosiveItem] | None = None,
    storage_id: str = "S",
) -> StorageBuilding:
    return StorageBuilding(
        name=f"Хранилище {storage_id}",
        storage_id=storage_id,
        category=WarehouseCategory.BASIS,
        duration=duration,
        location_type=location,
        is_bermed=is_bermed,
        items=items or [ExplosiveItem(name="ВВ", group=CompatibilityGroup.D, mass_kg=1000.0)],
    )


# --- Катящаяся сфера, СП РК 2.04-103-2013, формула (2-1) ---


def test_rolling_sphere_reference_values() -> None:
    assert rolling_sphere_radius(20.0, 0.0, 20.0) == pytest.approx(20.0)
    assert rolling_sphere_radius(14.5, 6.5, 20.0) == pytest.approx(math.sqrt(8.0 * 32.0))
    assert rolling_sphere_radius(14.5, 6.5, 20.0) == pytest.approx(16.0)
    assert rolling_sphere_radius(20.0, 0.0, 45.0) == pytest.approx(math.sqrt(20.0 * 70.0))


def test_rolling_sphere_no_protection_outside_formula_range() -> None:
    assert rolling_sphere_radius(10.0, 10.0, 20.0) == 0.0
    assert rolling_sphere_radius(10.0, 12.0, 20.0) == 0.0
    assert rolling_sphere_radius(45.0, 5.0, 20.0) == 0.0


def test_default_lightning_spec_is_sphere_level_one() -> None:
    spec = LightningSpec(masts=[LightningArresterMast(mast_id="M", x_m=10.0, y_m=0.0, height_h_m=15.0)])
    assert spec.method == LightningMethod.ROLLING_SPHERE_SP_RK
    assert spec.protection_level == LightningProtectionLevel.LEVEL_I
    assert spec.reliability == LightningReliability.P_0_999


def test_old_project_file_with_zone_type_keeps_rd_method() -> None:
    spec = LightningSpec.model_validate(
        {"zone_type": "zone_a", "masts": [{"mast_id": "M", "x_m": 10.0, "y_m": 0.0, "height_h_m": 15.0}]}
    )
    assert spec.method == LightningMethod.ZONES_RD_34_21_122


def test_zone_type_with_sphere_method_is_rejected() -> None:
    mast = LightningArresterMast(mast_id="M", x_m=10.0, y_m=0.0, height_h_m=15.0)
    with pytest.raises(ValueError):
        calculate_lightning_protection(
            [mast], LightningZoneType.ZONE_A, 6.0, 6.0, 4.0, 5.0, method=LightningMethod.ROLLING_SPHERE_SP_RK
        )


def test_sphere_solver_height_is_minimal() -> None:
    checkpoints = generate_storage_checkpoints_3d(12.0, 8.0, 5.0, 6.5)
    positions = [(11.5, 0.0)]
    height = solve_common_arrester_height(positions, checkpoints)
    assert height is not None
    assert all_points_covered(positions, height, checkpoints)
    assert not all_points_covered(positions, round(height - 0.1, 1), checkpoints)


# --- СО 153-34.21.122-2003, табл. 3.4 и формула (3.1) ---


@pytest.mark.parametrize(
    ("reliability", "height", "h0", "r0"),
    [
        ("0.9", 50.0, 42.5, 60.0),
        ("0.9", 120.0, 102.0, (1.2 - 0.02) * 120.0),
        ("0.99", 20.0, 16.0, 16.0),
        ("0.99", 50.0, 40.0, (0.8 - 1.43e-3 * 20.0) * 50.0),
        ("0.99", 120.0, (0.8 - 0.02) * 120.0, 84.0),
        ("0.999", 25.0, 17.5, 15.0),
        ("0.999", 50.0, (0.7 - 7.14e-4 * 20.0) * 50.0, (0.6 - 1.43e-3 * 20.0) * 50.0),
        ("0.999", 120.0, (0.65 - 0.02) * 120.0, (0.5 - 0.04) * 120.0),
    ],
)
def test_so153_table_3_4(reliability: str, height: float, h0: float, r0: float) -> None:
    assert so153_cone_parameters(height, reliability) == pytest.approx((h0, r0))


def test_so153_formula_3_1() -> None:
    h0, r0, rx = so153_single_rod_zone(25.0, 6.5, "0.999")
    assert (h0, r0) == pytest.approx((17.5, 15.0))
    assert rx == pytest.approx(15.0 * (17.5 - 6.5) / 17.5)
    assert so153_single_rod_zone(25.0, 17.5, "0.999")[2] == 0.0


@pytest.mark.parametrize("reliability", ["0.9", "0.99", "0.999"])
@pytest.mark.parametrize("boundary", [30.0, 100.0])
def test_so153_ranges_join_at_boundaries(reliability: str, boundary: float) -> None:
    below = so153_cone_parameters(boundary - 1e-9, reliability)
    above = so153_cone_parameters(boundary + 1e-9, reliability)
    assert below == pytest.approx(above, rel=1e-3)


def test_so153_higher_reliability_needs_higher_masts() -> None:
    checkpoints = generate_storage_checkpoints_3d(6.0, 8.0, 5.0, 6.5)
    positions = [(8.5, 0.0), (-8.5, 0.0)]
    heights = [
        solve_common_arrester_height(positions, checkpoints, method=LightningMethod.SINGLE_ROD_SO_153, reliability=p)
        for p in ("0.9", "0.99", "0.999")
    ]
    assert heights[0] < heights[1] < heights[2]
    best = heights[2]
    kwargs = {"method": LightningMethod.SINGLE_ROD_SO_153, "reliability": "0.999"}
    assert all_points_covered(positions, best, checkpoints, **kwargs)
    assert not all_points_covered(positions, round(best - 0.1, 1), checkpoints, **kwargs)


# --- Обязательность молниезащиты, п. 691 и 693 Приказа № 343 ---


def _codes_for_storage_without_lightning(duration: WarehouseDuration, location: LocationType) -> set[str]:
    definition = build_sample_project_definition()
    storages = [
        storage.model_copy(update={"duration": duration, "location_type": location})
        for storage in definition.project.storages
    ]
    designs = [design.model_copy(update={"lightning": None}) for design in definition.storage_designs]
    project = definition.project.model_copy(update={"storages": storages})
    result = calculate_project(definition.model_copy(update={"project": project, "storage_designs": designs}))
    return {violation.code for violation in result.validation.violations}


def test_permanent_storage_without_lightning_is_violation() -> None:
    assert "LIGHTNING_REQUIRED" in _codes_for_storage_without_lightning(
        WarehouseDuration.PERMANENT, LocationType.SURFACE
    )


def test_short_term_storage_may_have_no_lightning() -> None:
    assert "LIGHTNING_REQUIRED" not in _codes_for_storage_without_lightning(
        WarehouseDuration.SHORT_TERM, LocationType.SURFACE
    )


def test_sample_project_with_lightning_on_both_storages_is_compliant() -> None:
    result = calculate_project(build_sample_project_definition())
    methods = {record.method for record in result.lightning_records}
    assert methods == {LightningMethod.ROLLING_SPHERE_SP_RK, LightningMethod.SINGLE_ROD_SO_153}
    assert result.is_compliant


# --- Таблица 3 Приложения 11 ---


def test_table_3_formulas_reproduce_table_cells() -> None:
    tables = load_appendix11_tables()
    table = tables["table_3_uvv"]
    placements = {"buried": ChargePlacementType.BURIED_OWN_HEIGHT, "open": ChargePlacementType.OPEN_SURFACE}
    checked = 0
    for category, rows in table["categories"].items():
        for key, placement in placements.items():
            row = rows[key]
            if row is None:
                continue
            for mass, value in zip(table["masses_kg"], row["table_m"], strict=True):
                by_formula = table3_uvv_distance(int(category), placement, mass, tables)[2]
                if (category, key, mass) in TABLE3_KNOWN_ROUNDING_CELLS:
                    assert by_formula >= value
                    assert by_formula <= value * 1.12
                else:
                    assert by_formula == pytest.approx(value, rel=0.03)
                checked += 1
    assert checked == 60


def test_table_3_open_row_for_category_3_is_missing() -> None:
    with pytest.raises(ValueError):
        table3_uvv_distance(3, ChargePlacementType.OPEN_SURFACE, 10000.0, load_appendix11_tables())


def test_table_3_mass_above_table_range_is_rejected() -> None:
    with pytest.raises(ValueError):
        table3_uvv_distance(1, ChargePlacementType.OPEN_SURFACE, 300000.0, load_appendix11_tables())


def test_table_3_placement_by_berm_or_burial() -> None:
    assert table3_charge_placement(_storage(is_bermed=True)) == ChargePlacementType.BURIED_OWN_HEIGHT
    assert table3_charge_placement(_storage(location=LocationType.BURIED)) == ChargePlacementType.BURIED_OWN_HEIGHT
    assert table3_charge_placement(_storage()) == ChargePlacementType.OPEN_SURFACE


def test_table_3_uses_mass_of_largest_storage() -> None:
    small = _storage(storage_id="A", items=[ExplosiveItem(name="ВВ", group=CompatibilityGroup.D, mass_kg=4000.0)])
    large = _storage(storage_id="B", items=[ExplosiveItem(name="ВВ", group=CompatibilityGroup.D, mass_kg=25000.0)])
    target = ExternalProtectedObject(
        object_id="T", name="Поселок", allowed_damage_degree=2, actual_distance_m=500.0, table3_object_category=2
    )
    results = SafeDistanceEngine(uvv_method=UVVMethod.TABLE_3).uvv_matrix([small, large], [target])
    expected = 30.0 * 25000.0 ** (1.0 / 3.0)
    assert [result.required_distance_m for result in results] == pytest.approx([expected, expected])
    assert all(result.method == UVVMethod.TABLE_3 for result in results)
    assert all(result.violations[0].code == "UVV_SAFE_DISTANCE_TABLE_3" for result in results)


def test_table_3_requires_object_category() -> None:
    target = ExternalProtectedObject(object_id="T", name="Дорога", allowed_damage_degree=4, actual_distance_m=500.0)
    with pytest.raises(ValueError):
        SafeDistanceEngine(uvv_method=UVVMethod.TABLE_3).uvv(_storage(), target)


def test_pipeline_table_3_missing_category_is_reported_as_issue() -> None:
    definition = build_sample_project_definition()
    settings = definition.settings.model_copy(update={"uvv_method": UVVMethod.TABLE_3})
    result = calculate_project(definition.model_copy(update={"settings": settings}))
    assert result.uvv_results == []
    assert {issue.module for issue in result.errors} == {"uvv"}


# --- Шифры по Приложению 3 ТР ТС 028/2012 ---


@pytest.mark.parametrize(
    ("group", "subclass", "valid"),
    [
        (CompatibilityGroup.D, "1.1", True),
        (CompatibilityGroup.D, "1.5", True),
        (CompatibilityGroup.D, "1.3", False),
        (CompatibilityGroup.B, "1.4", True),
        (CompatibilityGroup.B, "1.3", False),
        (CompatibilityGroup.S, "1.1", False),
        (CompatibilityGroup.N, "1.6", True),
        (CompatibilityGroup.C, "1.3", True),
    ],
)
def test_tr_ts_classification_codes(group: CompatibilityGroup, subclass: str, valid: bool) -> None:
    storage = _storage(items=[ExplosiveItem(name="ВМ", group=group, mass_kg=100.0, hazard_subclass=subclass)])
    codes = {violation.code for violation in check_classification_codes(storage).violations}
    assert ("CLASSIFICATION_CODE_INVALID" not in codes) is valid


def test_group_a_is_absent_in_tr_ts() -> None:
    storage = _storage(items=[ExplosiveItem(name="ВМ", group=CompatibilityGroup.A, mass_kg=100.0)])
    assert [v.code for v in check_classification_codes(storage).violations] == ["CLASSIFICATION_CODE_INVALID"]
