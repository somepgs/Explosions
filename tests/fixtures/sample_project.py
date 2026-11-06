"""Демонстрационный файл проекта: два обвалованных хранилища, мачты молниезащиты, внешние объекты.

Все расчетные записи получаются через единый конвейер `calculate_project`, а не собираются вручную.
ВВ — на основе аммиачной селитры, группа совместимости D (Приложение 2), класс таблицы 4 — an_based.
Автодорога с небольшим движением — 4-я степень повреждения (примечание к таблице 2 Приложения 11).
Молниезащита (п. 691): S1 — катящаяся сфера СП РК уровня I; S2 — табл. 3.4 СО 153-34.21.122-2003, надежность 0,999.
"""

from dataclasses import dataclass

from explosions_core.calc.storage_sizing import StorageSizingCalculator
from explosions_core.domain import (
    BermRecord,
    BermSoilMaterial,
    BermSpec,
    CompatibilityGroup,
    DetonationMaterialClass,
    DetonationPairResult,
    ExplosiveItem,
    ExternalProtectedObject,
    LightningArresterMast,
    LightningMethod,
    LightningRecord,
    LightningReliability,
    LightningSpec,
    LocationType,
    PackagingType,
    ProjectCalculationResult,
    ProjectDefinition,
    StorageBuilding,
    StorageDesignInput,
    StorageMethod,
    StorageSizingInput,
    StorageSizingRecord,
    UnitPackageSpec,
    UnloadingPlatformConfig,
    UVVDistanceResult,
    WarehouseCategory,
    WarehouseDuration,
    WarehouseProjectInput,
)
from explosions_core.pipeline import calculate_project

SAMPLE_WALL_THICKNESS_M = 0.40
SAMPLE_DEFAULT_CLEAR_DISTANCE_M = 110.0
SAMPLE_EAVES_HEIGHT_M = 5.0
SAMPLE_RIDGE_HEIGHT_M = 6.5
SAMPLE_BERM_SLOPE_DEG = 45.0
SAMPLE_MAST_CLEARANCE_FROM_WALL_M = 5.5
SAMPLE_SO153_MAST_HEIGHT_M = 25.0
SAMPLE_BAG_UNIT = UnitPackageSpec(
    net_weight_kg=25.0,
    gross_weight_kg=26.0,
    length_m=0.55,
    width_m=0.35,
    height_m=0.15,
)
SAMPLE_FIRST_MASS_KG = 16000.0
SAMPLE_SECOND_MASS_KG = 5000.0


@dataclass(frozen=True)
class SampleNoteData:
    project: WarehouseProjectInput
    sizing_records: list[StorageSizingRecord]
    detonation_results: list[DetonationPairResult]
    uvv_results: list[UVVDistanceResult]
    berm_records: list[BermRecord]
    lightning_records: list[LightningRecord]


def build_sample_project_definition(
    clear_distance_m: float = SAMPLE_DEFAULT_CLEAR_DISTANCE_M,
) -> ProjectDefinition:
    first_length = _building_length(SAMPLE_FIRST_MASS_KG)
    storages = [
        _build_storage("S1", "Хранилище №1", SAMPLE_FIRST_MASS_KG, 0.0),
        _build_storage("S2", "Хранилище №2", SAMPLE_SECOND_MASS_KG, first_length + clear_distance_m),
    ]
    project = WarehouseProjectInput(
        name="Демонстрационный склад ВМ (тестовые данные)",
        storages=storages,
        forbidden_zone_width_m=50.0,
        fence_height_m=2.5,
        fence_to_nearest_storage_m=40.0,
        fence_to_guardhouse_m=50.0,
        fence_to_tare_storage_m=25.0,
        open_fire_ban_radius_m=100.0,
        unloading_platform=UnloadingPlatformConfig(
            fence_height_m=2.0,
            loading_point_to_fence_m=15.0,
            switch_distance_m=50.0,
            guardhouse_distance_m=50.0,
        ),
        external_targets=[
            ExternalProtectedObject(
                object_id="ROAD",
                name="Автомобильная дорога с небольшим движением",
                allowed_damage_degree=4,
                actual_distance_m=800.0,
            ),
            ExternalProtectedObject(
                object_id="LEP",
                name="Воздушная линия электропередачи 10 кВ",
                allowed_damage_degree=3,
                actual_distance_m=600.0,
            ),
        ],
    )
    return ProjectDefinition(
        project=project,
        storage_designs=[
            _build_design("S1", SAMPLE_FIRST_MASS_KG, _sphere_lightning(SAMPLE_FIRST_MASS_KG)),
            _build_design("S2", SAMPLE_SECOND_MASS_KG, _so153_lightning(SAMPLE_SECOND_MASS_KG)),
        ],
    )


def build_sample_project_result(
    clear_distance_m: float = SAMPLE_DEFAULT_CLEAR_DISTANCE_M,
) -> ProjectCalculationResult:
    return calculate_project(build_sample_project_definition(clear_distance_m))


def build_sample_note_data(clear_distance_m: float = SAMPLE_DEFAULT_CLEAR_DISTANCE_M) -> SampleNoteData:
    result = build_sample_project_result(clear_distance_m)
    return SampleNoteData(
        project=result.project,
        sizing_records=result.sizing_records,
        detonation_results=result.detonation_results,
        uvv_results=result.uvv_results,
        berm_records=result.berm_records,
        lightning_records=result.lightning_records,
    )


def _sizing_for(mass_kg: float) -> StorageSizingInput:
    return StorageSizingInput(
        total_net_explosive_mass_kg=mass_kg,
        compatibility_group=CompatibilityGroup.D,
        storage_method=StorageMethod.STACK,
        packaging_type=PackagingType.BAG,
        unit_spec=SAMPLE_BAG_UNIT,
        wall_racks_count=0,
        island_rows_count=4,
        cross_aisles_count=2,
    )


def _building_length(mass_kg: float) -> float:
    result = StorageSizingCalculator().calculate(_sizing_for(mass_kg))
    return result.min_internal_length_m + 2.0 * SAMPLE_WALL_THICKNESS_M


def _build_storage(storage_id: str, name: str, mass_kg: float, x_m: float) -> StorageBuilding:
    return StorageBuilding(
        name=name,
        storage_id=storage_id,
        category=WarehouseCategory.BASIS,
        duration=WarehouseDuration.PERMANENT,
        location_type=LocationType.SURFACE,
        is_bermed=True,
        items=[
            ExplosiveItem(
                name=f"Демонстрационное ВВ на основе АС, партия {storage_id}",
                group=CompatibilityGroup.D,
                mass_kg=mass_kg,
                tnt_equivalent_coeff=1.0,
                hazard_subclass="1.1",
                detonation_class=DetonationMaterialClass.AN_BASED,
            )
        ],
        x_m=x_m,
        y_m=0.0,
    )


def _mast_x(mass_kg: float) -> float:
    return _building_length(mass_kg) / 2.0 + SAMPLE_MAST_CLEARANCE_FROM_WALL_M


def _sphere_lightning(mass_kg: float) -> LightningSpec:
    mast_x = _mast_x(mass_kg)
    return LightningSpec(
        masts=[
            LightningArresterMast(mast_id="M1", x_m=mast_x, y_m=0.0, height_h_m=14.5),
            LightningArresterMast(mast_id="M2", x_m=-mast_x, y_m=0.0, height_h_m=22.0),
        ],
    )


def _so153_lightning(mass_kg: float) -> LightningSpec:
    mast_x = _mast_x(mass_kg)
    return LightningSpec(
        method=LightningMethod.SINGLE_ROD_SO_153,
        reliability=LightningReliability.P_0_999,
        masts=[
            LightningArresterMast(mast_id="M3", x_m=mast_x, y_m=0.0, height_h_m=SAMPLE_SO153_MAST_HEIGHT_M),
            LightningArresterMast(mast_id="M4", x_m=-mast_x, y_m=0.0, height_h_m=SAMPLE_SO153_MAST_HEIGHT_M),
        ],
    )


def _build_design(storage_id: str, mass_kg: float, lightning: LightningSpec | None) -> StorageDesignInput:
    return StorageDesignInput(
        storage_id=storage_id,
        sizing=_sizing_for(mass_kg),
        eaves_height_m=SAMPLE_EAVES_HEIGHT_M,
        ridge_height_m=SAMPLE_RIDGE_HEIGHT_M,
        berm=BermSpec(
            soil_material=BermSoilMaterial.PLASTIC_CLAY_LOAM,
            natural_slope_angle_deg=SAMPLE_BERM_SLOPE_DEG,
        ),
        lightning=lightning,
    )
