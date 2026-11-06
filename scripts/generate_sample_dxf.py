"""Генерация эталонных DXF-чертежей склада ВМ в папку output_dxf/ для открытия в nanoCAD."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from explosions_core.calc.berm_calculator import calculate_berm_design  # noqa: E402
from explosions_core.calc.lightning_protection import calculate_lightning_protection  # noqa: E402
from explosions_core.calc.safe_distances import SafeDistanceEngine  # noqa: E402
from explosions_core.calc.storage_sizing import StorageSizingCalculator  # noqa: E402
from explosions_core.domain import (  # noqa: E402
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
from explosions_core.export.cad.master_plan_dxf import export_master_plan_dxf  # noqa: E402
from explosions_core.export.cad.storage_detail_dxf import export_storage_detail_dxf  # noqa: E402

OUTPUT_DIR = PROJECT_ROOT / "output_dxf"
STORAGE_LENGTH_M = 20.0
STORAGE_WIDTH_M = 10.0


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
        storage_length_m=STORAGE_LENGTH_M,
        storage_width_m=STORAGE_WIDTH_M,
        eaves_height_m=3.5,
        soil_material=BermSoilMaterial.PLASTIC_CLAY_LOAM,
        natural_slope_angle_deg=45.0,
    )


def _storage(name: str, storage_id: str, x_m: float, y_m: float, mass_kg: float) -> StorageBuilding:
    return StorageBuilding(
        name=name,
        storage_id=storage_id,
        category=WarehouseCategory.BASIS,
        duration=WarehouseDuration.PERMANENT,
        location_type=LocationType.SURFACE,
        is_bermed=True,
        items=[
            ExplosiveItem(
                name="ВВ",
                group=CompatibilityGroup.B,
                mass_kg=mass_kg,
                tnt_equivalent_coeff=1.0,
            )
        ],
        x_m=x_m,
        y_m=y_m,
        length_m=STORAGE_LENGTH_M,
        width_m=STORAGE_WIDTH_M,
        stack_width_b_m=1.6,
    )


def _project_input() -> WarehouseProjectInput:
    return WarehouseProjectInput(
        name="Склад ВМ карьера",
        storages=[
            _storage("Хранилище 1", "S1", 0.0, 0.0, 16000.0),
            _storage("Хранилище 2", "S2", 60.0, 0.0, 5000.0),
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


def main() -> None:
    sizing_input = _storage_sizing_input()
    sizing_result = StorageSizingCalculator().calculate(sizing_input)
    berm_input = _berm_input()
    berm_result = calculate_berm_design(berm_input)
    masts = [
        LightningArresterMast(mast_id="М1", x_m=-15.0, y_m=10.0, height_h_m=16.0),
        LightningArresterMast(mast_id="М2", x_m=15.0, y_m=-10.0, height_h_m=16.0),
    ]
    lightning_result = calculate_lightning_protection(
        masts,
        LightningZoneType.ZONE_A,
        storage_length_m=STORAGE_LENGTH_M,
        storage_width_m=STORAGE_WIDTH_M,
        eaves_height_m=3.5,
        ridge_height_m=5.5,
    )

    detail_path = export_storage_detail_dxf(
        sizing_input,
        sizing_result,
        berm_input,
        berm_result,
        masts,
        lightning_result,
        OUTPUT_DIR / "storage_detail.dxf",
    )

    project = _project_input()
    engine = SafeDistanceEngine()
    s1, s2 = project.storages
    detonation_results = [engine.detonation_pair(s1, s2)]
    uvv_results = [engine.uvv(s1, target) for target in project.external_targets]
    berm_results = {
        "S1": calculate_berm_design(berm_input),
        "S2": calculate_berm_design(berm_input),
    }
    master_path = export_master_plan_dxf(
        project,
        detonation_results,
        uvv_results,
        berm_results,
        OUTPUT_DIR / "master_plan_safety_zones.dxf",
    )

    print(f"Сохранено: {detail_path}")
    print(f"Сохранено: {master_path}")


if __name__ == "__main__":
    main()
