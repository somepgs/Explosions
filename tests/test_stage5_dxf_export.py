import ezdxf
import pytest

from explosions_core.export.cad.dxf_styles import (
    LAYER_BERM_CREST,
    LAYER_BERM_TOE,
    LAYER_DIMENSIONS,
    LAYER_LIGHTNING,
    LAYER_PERIMETER,
    LAYER_RACKS,
    LAYER_SAFE_RD,
    LAYER_SAFE_UVV,
    LAYER_WALLS,
    LAYERS,
    TEXT_FONT,
    TEXT_STYLE_NAME,
    create_document,
    draw_slope_berm_ticks,
)
from explosions_core.export.cad.master_plan_dxf import export_master_plan_dxf
from explosions_core.export.cad.storage_detail_dxf import export_storage_detail_dxf
from explosions_core.calc.berm_calculator import calculate_berm_design
from explosions_core.calc.lightning_protection import calculate_lightning_protection
from explosions_core.calc.safe_distances import SafeDistanceEngine
from explosions_core.calc.storage_sizing import StorageSizingCalculator
from explosions_core.domain import (
    BermDesignInput,
    BermSoilMaterial,
    CompatibilityGroup,
    ExplosiveItem,
    ExternalProtectedObject,
    LightningArresterMast,
    LightningZoneType,
    LocationType,
    PackagingType,
    StorageBuilding,
    StorageMethod,
    StorageSizingInput,
    UnitPackageSpec,
    WarehouseCategory,
    WarehouseDuration,
    WarehouseProjectInput,
)

EXPECTED_LAYER_NAMES = {spec.name for spec in LAYERS}


def _storage_sizing_input() -> StorageSizingInput:
    return StorageSizingInput(
        total_net_explosive_mass_kg=40000.0,
        compatibility_group=CompatibilityGroup.B,
        storage_method=StorageMethod.STACK,
        packaging_type=PackagingType.BAG,
        unit_spec=UnitPackageSpec(
            net_weight_kg=25.0,
            gross_weight_kg=25.5,
            length_m=0.55,
            width_m=0.35,
            height_m=0.15,
        ),
        island_rows_count=4,
        wall_racks_count=0,
    )


def _berm_input() -> BermDesignInput:
    return BermDesignInput(
        storage_length_m=20.0,
        storage_width_m=10.0,
        eaves_height_m=3.5,
        soil_material=BermSoilMaterial.PLASTIC_CLAY_LOAM,
        natural_slope_angle_deg=45.0,
    )


def _masts() -> list[LightningArresterMast]:
    return [
        LightningArresterMast(mast_id="М1", x_m=-15.0, y_m=10.0, height_h_m=16.0),
        LightningArresterMast(mast_id="М2", x_m=15.0, y_m=-10.0, height_h_m=16.0),
    ]


def _storage_detail_inputs():
    sizing_input = _storage_sizing_input()
    sizing_result = StorageSizingCalculator().calculate(sizing_input)
    berm_input = _berm_input()
    berm_result = calculate_berm_design(berm_input)
    masts = _masts()
    lightning_result = calculate_lightning_protection(
        masts,
        LightningZoneType.ZONE_A,
        storage_length_m=20.0,
        storage_width_m=10.0,
        eaves_height_m=3.5,
        ridge_height_m=5.5,
    )
    return sizing_input, sizing_result, berm_input, berm_result, masts, lightning_result


def _storage(name: str, storage_id: str, x_m: float, y_m: float, items: list[ExplosiveItem]) -> StorageBuilding:
    return StorageBuilding(
        name=name,
        storage_id=storage_id,
        category=WarehouseCategory.BASIS,
        duration=WarehouseDuration.PERMANENT,
        location_type=LocationType.SURFACE,
        is_bermed=True,
        items=items,
        x_m=x_m,
        y_m=y_m,
        length_m=20.0,
        width_m=10.0,
        stack_width_b_m=1.6,
    )


def _project_input() -> WarehouseProjectInput:
    items_1 = [ExplosiveItem(name="ВВ", group=CompatibilityGroup.B, mass_kg=16000.0, tnt_equivalent_coeff=1.0)]
    items_2 = [ExplosiveItem(name="ВВ", group=CompatibilityGroup.B, mass_kg=5000.0, tnt_equivalent_coeff=1.0)]
    return WarehouseProjectInput(
        name="Склад",
        storages=[
            _storage("Хранилище 1", "S1", 0.0, 0.0, items_1),
            _storage("Хранилище 2", "S2", 60.0, 0.0, items_2),
        ],
        external_targets=[
            ExternalProtectedObject(
                object_id="ROAD",
                name="Автодорога",
                allowed_damage_degree=2,
                actual_distance_m=150.0,
                bearing_deg=90.0,
            ),
            ExternalProtectedObject(
                object_id="POWER",
                name="ЛЭП",
                allowed_damage_degree=3,
                actual_distance_m=220.0,
                bearing_deg=270.0,
            ),
        ],
    )


def _master_plan_inputs():
    project = _project_input()
    engine = SafeDistanceEngine()
    s1, s2 = project.storages
    detonation = engine.detonation_pair(s1, s2)
    uvv = [engine.uvv(s1, target) for target in project.external_targets]
    berm_results = {
        "S1": calculate_berm_design(_berm_input()),
        "S2": calculate_berm_design(_berm_input()),
    }
    return project, [detonation], uvv, berm_results


def _layer_entities(doc, layer: str, dxftype: str | None = None):
    msp = doc.modelspace()
    result = []
    for entity in msp:
        if entity.dxf.layer != layer:
            continue
        if dxftype is None or entity.dxftype() == dxftype:
            result.append(entity)
    return result


def test_export_storage_detail_dxf(tmp_path):
    sizing_input, sizing_result, berm_input, berm_result, masts, lightning_result = _storage_detail_inputs()
    output_path = tmp_path / "storage_detail.dxf"

    result_path = export_storage_detail_dxf(
        sizing_input,
        sizing_result,
        berm_input,
        berm_result,
        masts,
        lightning_result,
        output_path,
    )

    assert result_path == output_path
    assert output_path.exists()
    doc = ezdxf.readfile(output_path, encoding="utf-8")
    assert doc.dxfversion == "AC1024"
    assert doc.header["$INSUNITS"] == 6
    assert EXPECTED_LAYER_NAMES.issubset({layer.dxf.name for layer in doc.layers})
    assert doc.styles.has_entry(TEXT_STYLE_NAME)
    assert doc.styles.get(TEXT_STYLE_NAME).dxf.font == TEXT_FONT

    racks = _layer_entities(doc, LAYER_RACKS, "LWPOLYLINE")
    assert len(racks) >= 4

    berm_crest = _layer_entities(doc, LAYER_BERM_CREST, "LWPOLYLINE")
    assert berm_crest
    berm_toe = _layer_entities(doc, LAYER_BERM_TOE, "LWPOLYLINE")
    assert berm_toe

    lightning_circles = _layer_entities(doc, LAYER_LIGHTNING, "CIRCLE")
    expected_circles = sum(
        sum(1 for key in ("r0_ground_m", "rx_at_eaves_m", "rx_at_ridge_m") if float(ring[key]) > 0.0)
        for ring in lightning_result.mast_results
    )
    assert len(lightning_circles) == expected_circles
    assert len(lightning_circles) == 3 * len(masts)

    dimensions = _layer_entities(doc, LAYER_DIMENSIONS, "DIMENSION")
    assert dimensions


def test_export_master_plan_dxf(tmp_path):
    project, detonation, uvv, berm_results = _master_plan_inputs()
    output_path = tmp_path / "master_plan_safety_zones.dxf"

    result_path = export_master_plan_dxf(project, detonation, uvv, berm_results, output_path)

    assert result_path == output_path
    doc = ezdxf.readfile(output_path, encoding="utf-8")
    assert doc.dxfversion == "AC1024"

    rd_radii = sorted(circle.dxf.radius for circle in _layer_entities(doc, LAYER_SAFE_RD, "CIRCLE"))
    expected_rd = sorted([detonation[0].r_d_i_to_j_m, detonation[0].r_d_j_to_i_m])
    assert rd_radii == pytest.approx(expected_rd, abs=1e-4)

    uvv_radii = sorted(circle.dxf.radius for circle in _layer_entities(doc, LAYER_SAFE_UVV, "CIRCLE"))
    expected_uvv = sorted(result.required_distance_m for result in uvv)
    assert uvv_radii == pytest.approx(expected_uvv, abs=1e-4)

    assert _layer_entities(doc, LAYER_PERIMETER)
    assert _layer_entities(doc, LAYER_WALLS)


def test_draw_slope_berm_ticks_alternates_full_and_half_length():
    doc = create_document()
    msp = doc.modelspace()

    count = draw_slope_berm_ticks(msp, (0.0, 0.0), (4.0, 0.0), (0.0, -2.0), (4.0, -2.0), step_m=1.0, layer=LAYER_BERM_TOE)

    ticks = _layer_entities(doc, LAYER_BERM_TOE, "LINE")
    assert count == 5
    lengths = sorted(round(_line_length(tick), 6) for tick in ticks)
    assert lengths.count(2.0) == 3
    assert lengths.count(1.0) == 2


def _line_length(entity) -> float:
    start = entity.dxf.start
    end = entity.dxf.end
    return ((end.x - start.x) ** 2 + (end.y - start.y) ** 2) ** 0.5


def test_document_layers_match_gost_registry():
    doc = create_document()
    layers = {layer.dxf.name: layer for layer in doc.layers}

    for spec in LAYERS:
        assert spec.name in layers
        assert layers[spec.name].dxf.color == spec.color
        assert layers[spec.name].dxf.linetype == spec.linetype
        assert layers[spec.name].dxf.lineweight == spec.lineweight
        assert isinstance(layers[spec.name].dxf.lineweight, int)
    assert doc.header["$MEASUREMENT"] == 1
