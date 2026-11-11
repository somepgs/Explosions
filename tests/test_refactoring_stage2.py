from pathlib import Path

import ezdxf
import pytest

from explosions_core.export.cad.master_plan_dxf import export_master_plan_dxf
from explosions_core.calc.geometry import (
    clear_distance_between,
    nearest_point,
    storage_bounds,
    storage_center,
    storage_key,
    storages_bounds,
)
from explosions_core.calc.lightning_protection import (
    generate_storage_checkpoints_3d,
    solve_common_arrester_height,
    solve_minimum_arrester_height,
)
from explosions_core.calc.safe_distances import SafeDistanceEngine, calculate_clear_distance, calculate_tnt_equivalent_mass
from explosions_core.domain import (
    ChargePlacementType,
    CompatibilityGroup,
    DetonationMaterialClass,
    ExplosiveItem,
    LightningZoneType,
    LocationType,
    StorageBuilding,
    WarehouseCategory,
    WarehouseDuration,
)
from tests.fixtures.sample_project import build_sample_note_data


def _storage(name: str, x_m: float, y_m: float, length_m: float, width_m: float) -> StorageBuilding:
    return StorageBuilding(
        name=name,
        storage_id=name,
        category=WarehouseCategory.BASIS,
        duration=WarehouseDuration.PERMANENT,
        location_type=LocationType.SURFACE,
        items=[
            ExplosiveItem(
                name="ВВ",
                group=CompatibilityGroup.D,
                mass_kg=1000.0,
                tnt_equivalent_coeff=1.0,
                detonation_class=DetonationMaterialClass.AN_BASED,
            )
        ],
        x_m=x_m,
        y_m=y_m,
        length_m=length_m,
        width_m=width_m,
    )


def test_geometry_clear_distance_and_nearest_point() -> None:
    left = _storage("L", 0.0, 0.0, 10.0, 10.0)
    right = _storage("R", 13.0, 14.0, 10.0, 10.0)
    assert storage_bounds(left) == (0.0, 0.0, 10.0, 10.0)
    assert storage_center(left) == (5.0, 5.0)
    assert clear_distance_between(left, right) == pytest.approx(5.0)
    assert calculate_clear_distance(left, right) == pytest.approx(5.0)
    assert nearest_point(left, right) == (10.0, 10.0)
    assert storage_key(left) == "L"


def test_storages_bounds_cover_all_buildings() -> None:
    first = _storage("A", 0.0, 0.0, 10.0, 10.0)
    second = _storage("B", 20.0, -5.0, 4.0, 6.0)
    assert storages_bounds([first, second]) == (0.0, -5.0, 24.0, 10.0)


def test_detonation_matrix_has_pair_for_each_combination() -> None:
    data = build_sample_note_data()
    storages = [*data.project.storages, _storage("S3", 300.0, 0.0, 8.0, 8.0)]
    results = SafeDistanceEngine().detonation_matrix(storages)
    assert len(results) == 3
    keys = {(result.storage_i_id, result.storage_j_id) for result in results}
    assert keys == {("S1", "S2"), ("S1", "S3"), ("S2", "S3")}


def test_detonation_matrix_matches_pairwise_calculation() -> None:
    data = build_sample_note_data()
    engine = SafeDistanceEngine()
    matrix = engine.detonation_matrix(data.project.storages)
    pairwise = engine.detonation_pair(data.project.storages[0], data.project.storages[1])
    assert len(matrix) == 1
    assert matrix[0].governing_required_r_d_m == pytest.approx(pairwise.governing_required_r_d_m)
    assert matrix[0].actual_clear_distance_m == pytest.approx(pairwise.actual_clear_distance_m)


def test_uvv_matrix_has_result_per_storage_and_target() -> None:
    data = build_sample_note_data()
    results = SafeDistanceEngine().uvv_matrix(
        data.project.storages, data.project.external_targets, ChargePlacementType.OPEN_SURFACE
    )
    assert len(results) == len(data.project.storages) * len(data.project.external_targets)
    pairs = {(result.storage_id, result.object_id) for result in results}
    assert ("S1", "ROAD") in pairs
    assert ("S2", "LEP") in pairs


def test_tnt_mass_skip_missing_ignores_items_without_coefficient() -> None:
    items = [
        ExplosiveItem(name="A", group=CompatibilityGroup.B, mass_kg=100.0, tnt_equivalent_coeff=1.0),
        ExplosiveItem(name="B", group=CompatibilityGroup.B, mass_kg=50.0),
    ]
    assert calculate_tnt_equivalent_mass(items, skip_missing=True) == pytest.approx(100.0)
    with pytest.raises(ValueError):
        calculate_tnt_equivalent_mass(items)


def test_common_height_covers_points_with_two_masts_not_higher_than_single() -> None:
    checkpoints = generate_storage_checkpoints_3d(12.0, 9.0, 6.0, 7.5)
    positions = [(-6.0, 0.0), (6.0, 0.0)]
    common = solve_common_arrester_height(positions, checkpoints, LightningZoneType.ZONE_A)
    assert common is not None
    singles = [
        solve_minimum_arrester_height(x, y, checkpoints, LightningZoneType.ZONE_A) for x, y in positions
    ]
    assert all(single is not None for single in singles)
    assert common <= min(singles)


def test_common_height_is_minimal_for_all_points() -> None:
    from explosions_core.calc.lightning_protection import all_points_covered

    checkpoints = generate_storage_checkpoints_3d(12.0, 9.0, 6.0, 7.5)
    positions = [(-6.0, 0.0), (6.0, 0.0)]
    common = solve_common_arrester_height(positions, checkpoints, LightningZoneType.ZONE_A)
    assert common is not None
    assert all_points_covered(positions, common, checkpoints, LightningZoneType.ZONE_A)
    assert not all_points_covered(positions, common - 0.1, checkpoints, LightningZoneType.ZONE_A)


def test_storage_gate_width_follows_entrance_opening(tmp_path: Path) -> None:
    from explosions_core.export.cad.storage_detail_dxf import export_storage_detail_dxf
    from explosions_core.calc.berm_calculator import calculate_berm_design
    from explosions_core.calc.lightning_protection import calculate_lightning_protection
    from explosions_core.calc.storage_sizing import StorageSizingCalculator
    from explosions_core.domain import (
        BermDesignInput,
        BermSoilMaterial,
        LightningArresterMast,
        PackagingType,
        StorageMethod,
        StorageSizingInput,
        UnitPackageSpec,
    )

    sizing_input = StorageSizingInput(
        total_net_explosive_mass_kg=40000.0,
        compatibility_group=CompatibilityGroup.B,
        storage_method=StorageMethod.STACK,
        packaging_type=PackagingType.BAG,
        unit_spec=UnitPackageSpec(net_weight_kg=25.0, gross_weight_kg=25.5, length_m=0.55, width_m=0.35, height_m=0.15),
        island_rows_count=4,
        wall_racks_count=0,
    )
    sizing_result = StorageSizingCalculator().calculate(sizing_input)
    berm_input = BermDesignInput(
        storage_length_m=20.0,
        storage_width_m=10.0,
        load_top_height_m=2.5,
        soil_material=BermSoilMaterial.PLASTIC_CLAY_LOAM,
        natural_slope_angle_deg=45.0,
        entrance_opening_width_m=3.0,
    )
    berm_result = calculate_berm_design(berm_input)
    masts = [LightningArresterMast(mast_id="М1", x_m=-15.0, y_m=10.0, height_h_m=16.0)]
    lightning_result = calculate_lightning_protection(
        masts, LightningZoneType.ZONE_A, 20.0, 10.0, 3.5, 5.5
    )
    output = tmp_path / "gate.dxf"
    export_storage_detail_dxf(
        sizing_input, sizing_result, berm_input, berm_result, masts, lightning_result, output
    )
    doc = ezdxf.readfile(output, encoding="utf-8")
    walls = [
        entity
        for entity in doc.modelspace().query("LWPOLYLINE")
        if entity.dxf.layer == "01_STORAGE_WALLS"
    ]
    outer = [entity for entity in walls if len(entity.get_points("xy")) == 6]
    assert outer, "outer wall polyline with gate not found"
    gate_ys = {round(abs(point[1]), 6) for point in outer[0].get_points("xy")}
    assert 1.5 in gate_ys
    assert 2.0 not in gate_ys


def test_master_plan_fire_ban_zone_is_built_from_storages_not_fence(tmp_path: Path) -> None:
    data = build_sample_note_data()
    output = tmp_path / "plan.dxf"
    export_master_plan_dxf(
        data.project,
        data.detonation_results,
        data.uvv_results,
        {record.storage_id: record.result for record in data.berm_records},
        output,
    )
    doc = ezdxf.readfile(output, encoding="utf-8")
    polylines = [
        entity
        for entity in doc.modelspace().query("LWPOLYLINE")
        if entity.dxf.layer == "07_PERIMETER_AND_ZONES"
    ]
    xs = [point[0] for entity in polylines for point in entity.get_points("xy")]
    ys = [point[1] for entity in polylines for point in entity.get_points("xy")]
    storages = data.project.storages
    bx1, by1, bx2, by2 = storages_bounds(storages)
    fire_x_min = min(xs)
    fire_y_min = min(ys)
    assert fire_x_min == pytest.approx(bx1 - 100.0, abs=1e-6)
    assert fire_y_min == pytest.approx(by1 - 100.0, abs=1e-6)
    assert max(xs) == pytest.approx(bx2 + 100.0, abs=1e-6)
    assert max(ys) == pytest.approx(by2 + 100.0, abs=1e-6)
