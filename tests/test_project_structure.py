import importlib

import pytest

import explosions_core
import explosions_core.domain as domain
from explosions_core.calc.safe_distances import DEFAULT_TABLES_PATH, load_appendix11_tables
from explosions_core.domain import (
    CompatibilityGroup,
    ExplosiveItem,
    LocationType,
    StorageBuilding,
    WarehouseCategory,
    WarehouseDuration,
    WarehouseProjectInput,
)
from explosions_core.norms import references
from explosions_core.validators.compatibility import check_storage_compatibility
from explosions_core.validators.layout_and_perimeter import validate_perimeter
from tests.fixtures.sample_project import SampleNoteData


def test_old_src_package_is_gone() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("src.models")


def test_package_has_version() -> None:
    assert explosions_core.__version__


@pytest.mark.parametrize(
    "module_name",
    ["enums", "results", "explosives", "storage", "sizing", "distances", "berm", "lightning"],
)
def test_domain_submodules_are_reexported(module_name: str) -> None:
    module = importlib.import_module(f"explosions_core.domain.{module_name}")
    public = [name for name, value in vars(module).items() if isinstance(value, type) and value.__module__ == module.__name__]
    assert public
    for name in public:
        assert name in domain.__all__
        assert getattr(domain, name) is getattr(module, name)


def test_project_input_accepts_external_targets_without_rebuild() -> None:
    project = WarehouseProjectInput.model_validate(
        {
            "name": "Склад",
            "external_targets": [
                {"object_id": "ROAD", "name": "Автодорога", "allowed_damage_degree": 2, "actual_distance_m": 150.0}
            ],
        }
    )
    assert project.external_targets[0].object_id == "ROAD"


def test_appendix11_tables_are_inside_package() -> None:
    assert DEFAULT_TABLES_PATH.is_file()
    assert DEFAULT_TABLES_PATH.parent.parent.name == "norms"
    tables = load_appendix11_tables()
    assert {"table_2_uvv", "table_4_kd", "table_5_rd_b_1_6_m"} <= set(tables)


def test_validators_cite_clauses_from_registry() -> None:
    storage = StorageBuilding(
        name="Х1",
        category=WarehouseCategory.BASIS,
        duration=WarehouseDuration.PERMANENT,
        location_type=LocationType.SURFACE,
        items=[
            ExplosiveItem(name="ВВ", group=CompatibilityGroup.B, mass_kg=100.0),
            ExplosiveItem(name="СИ", group=CompatibilityGroup.S, mass_kg=1.0),
        ],
    )
    assert check_storage_compatibility(storage).violations[0].clause == references.CLAUSE_COMPATIBILITY

    project = WarehouseProjectInput(name="Склад", open_fire_ban_radius_m=50.0)
    clauses = {violation.clause for violation in validate_perimeter(project).violations}
    assert references.CLAUSE_OPEN_FIRE in clauses


def test_npa_list_contains_order_343() -> None:
    assert any("30.12.2014 № 343" in npa for npa in references.NPA_LIST)


def test_sample_fixture_builds_project(sample_note_data: SampleNoteData) -> None:
    assert len(sample_note_data.project.storages) == 2
    assert sample_note_data.detonation_results
