"""Демонстрационные исходные данные эталонной записки: два обвалованных хранилища, мачты молниезащиты, внешние объекты."""

from dataclasses import dataclass

from explosions_core.calc.berm_calculator import calculate_berm_design
from explosions_core.calc.geometry import storage_key
from explosions_core.calc.lightning_protection import calculate_lightning_protection
from explosions_core.calc.safe_distances import SafeDistanceEngine
from explosions_core.calc.storage_sizing import StorageSizingCalculator
from explosions_core.domain import (
    BermDesignInput,
    BermSoilMaterial,
    ChargePlacementType,
    CompatibilityGroup,
    DetonationPairResult,
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
    UnloadingPlatformConfig,
    UVVDistanceResult,
    WarehouseCategory,
    WarehouseDuration,
    WarehouseProjectInput,
)
from explosions_core.export.reports.note.records import BermRecord, LightningRecord, StorageSizingRecord

SAMPLE_WALL_THICKNESS_M = 0.40
SAMPLE_DEFAULT_CLEAR_DISTANCE_M = 110.0
SAMPLE_EAVES_HEIGHT_M = 5.0
SAMPLE_RIDGE_HEIGHT_M = 6.5
SAMPLE_BERM_SLOPE_DEG = 45.0
SAMPLE_MAST_CLEARANCE_FROM_WALL_M = 5.5
SAMPLE_BAG_UNIT = UnitPackageSpec(
    net_weight_kg=25.0,
    gross_weight_kg=26.0,
    length_m=0.55,
    width_m=0.35,
    height_m=0.15,
)


@dataclass(frozen=True)
class SampleNoteData:
    project: WarehouseProjectInput
    sizing_records: list[StorageSizingRecord]
    detonation_results: list[DetonationPairResult]
    uvv_results: list[UVVDistanceResult]
    berm_records: list[BermRecord]
    lightning_records: list[LightningRecord]


def _build_storage(
    storage_id: str,
    name: str,
    mass_kg: float,
    x_m: float,
) -> tuple[StorageBuilding, StorageSizingRecord]:
    sizing_input = StorageSizingInput(
        total_net_explosive_mass_kg=mass_kg,
        compatibility_group=CompatibilityGroup.B,
        storage_method=StorageMethod.STACK,
        packaging_type=PackagingType.BAG,
        unit_spec=SAMPLE_BAG_UNIT,
        wall_racks_count=0,
        island_rows_count=4,
        cross_aisles_count=2,
    )
    sizing_result = StorageSizingCalculator().calculate(sizing_input)
    storage = StorageBuilding(
        name=name,
        storage_id=storage_id,
        category=WarehouseCategory.BASIS,
        duration=WarehouseDuration.PERMANENT,
        location_type=LocationType.SURFACE,
        is_bermed=True,
        items=[
            ExplosiveItem(
                name=f"Демонстрационное ВВ, партия {storage_id}",
                group=CompatibilityGroup.B,
                mass_kg=mass_kg,
                tnt_equivalent_coeff=1.0,
                hazard_subclass="1.1",
            )
        ],
        x_m=x_m,
        y_m=0.0,
        length_m=sizing_result.min_internal_length_m + 2 * SAMPLE_WALL_THICKNESS_M,
        width_m=sizing_result.min_internal_width_m + 2 * SAMPLE_WALL_THICKNESS_M,
    )
    return storage, StorageSizingRecord(storage_id=storage_id, sizing_input=sizing_input, result=sizing_result)


def build_sample_note_data(clear_distance_m: float = SAMPLE_DEFAULT_CLEAR_DISTANCE_M) -> SampleNoteData:
    storage_1, sizing_1 = _build_storage("S1", "Хранилище №1", 16000.0, 0.0)
    storage_2, sizing_2 = _build_storage(
        "S2",
        "Хранилище №2",
        5000.0,
        storage_1.length_m + clear_distance_m,
    )
    storages = [storage_1, storage_2]

    road = ExternalProtectedObject(
        object_id="ROAD",
        name="Автомобильная дорога общего пользования",
        allowed_damage_degree=2,
        actual_distance_m=800.0,
    )
    power_line = ExternalProtectedObject(
        object_id="LEP",
        name="Воздушная линия электропередачи 10 кВ",
        allowed_damage_degree=3,
        actual_distance_m=300.0,
    )
    project = WarehouseProjectInput(
        name="Демонстрационный склад ВМ (тестовые данные)",
        storages=storages,
        forbidden_zone_width_m=50.0,
        fence_height_m=2.0,
        fence_to_nearest_storage_m=40.0,
        fence_to_guardhouse_m=50.0,
        fence_to_tare_storage_m=25.0,
        open_fire_ban_radius_m=100.0,
        unloading_platform=UnloadingPlatformConfig(
            loading_point_to_fence_m=15.0,
            switch_distance_m=50.0,
            guardhouse_distance_m=50.0,
        ),
        external_targets=[road, power_line],
    )

    engine = SafeDistanceEngine()
    detonation_results = engine.detonation_matrix(storages)
    uvv_results = engine.uvv_matrix(storages, project.external_targets, ChargePlacementType.OPEN_SURFACE)

    berm_records: list[BermRecord] = []
    for storage in storages:
        berm_input = BermDesignInput(
            storage_length_m=storage.length_m,
            storage_width_m=storage.width_m,
            eaves_height_m=SAMPLE_EAVES_HEIGHT_M,
            soil_material=BermSoilMaterial.PLASTIC_CLAY_LOAM,
            natural_slope_angle_deg=SAMPLE_BERM_SLOPE_DEG,
        )
        berm_records.append(
            BermRecord(
                storage_id=storage_key(storage),
                berm_input=berm_input,
                result=calculate_berm_design(berm_input),
            )
        )

    mast_x = storage_1.length_m / 2.0 + SAMPLE_MAST_CLEARANCE_FROM_WALL_M
    masts = [
        LightningArresterMast(mast_id="M1", x_m=mast_x, y_m=0.0, height_h_m=14.5),
        LightningArresterMast(mast_id="M2", x_m=-mast_x, y_m=0.0, height_h_m=22.0),
    ]
    lightning_result = calculate_lightning_protection(
        masts,
        LightningZoneType.ZONE_A,
        storage_1.length_m,
        storage_1.width_m,
        SAMPLE_EAVES_HEIGHT_M,
        SAMPLE_RIDGE_HEIGHT_M,
    )
    lightning_records = [
        LightningRecord(
            storage_id=storage_key(storage_1),
            zone_type=LightningZoneType.ZONE_A,
            masts=masts,
            storage_length_m=storage_1.length_m,
            storage_width_m=storage_1.width_m,
            eaves_height_m=SAMPLE_EAVES_HEIGHT_M,
            ridge_height_m=SAMPLE_RIDGE_HEIGHT_M,
            result=lightning_result,
        )
    ]

    return SampleNoteData(
        project=project,
        sizing_records=[sizing_1, sizing_2],
        detonation_results=detonation_results,
        uvv_results=uvv_results,
        berm_records=berm_records,
        lightning_records=lightning_records,
    )
