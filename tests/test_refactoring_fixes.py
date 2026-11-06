from pathlib import Path

import docx
import ezdxf
import pytest

from explosions_core.export.cad.master_plan_dxf import export_master_plan_dxf
from explosions_core.norms.constants_rk343 import MAX_SHORT_TERM_SINGLE_STORAGE_VM_KG, MIN_SHELF_VERTICAL_GAP_M
from explosions_core.calc.berm_calculator import calculate_berm_design
from explosions_core.calc.safe_distances import load_appendix11_tables
from explosions_core.calc.storage_sizing import StorageSizingCalculator
from explosions_core.domain import (
    BermDesignInput,
    BermSoilMaterial,
    CompatibilityGroup,
    ExplosiveItem,
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
from explosions_core.export.reports.docx_styles import RED
from explosions_core.export.reports.explanatory_note_docx import export_explanatory_note_docx
from tests.fixtures.sample_project import build_sample_note_data
from explosions_core.validators.layout_and_perimeter import validate_short_term_limits


def _sizing_input(method: StorageMethod, gap_m: float) -> StorageSizingInput:
    return StorageSizingInput(
        total_net_explosive_mass_kg=40000.0,
        compatibility_group=CompatibilityGroup.B,
        storage_method=method,
        packaging_type=PackagingType.BAG,
        unit_spec=UnitPackageSpec(
            net_weight_kg=25.0,
            gross_weight_kg=26.0,
            length_m=0.55,
            width_m=0.35,
            height_m=0.15,
        ),
        shelf_vertical_gap_m=gap_m,
    )


def _violation_codes(result) -> list[str]:
    return [violation.code for violation in result.violations]


def test_stack_with_small_shelf_gap_has_no_shelf_gap_violation() -> None:
    result = StorageSizingCalculator().calculate(
        _sizing_input(StorageMethod.STACK, gap_m=MIN_SHELF_VERTICAL_GAP_M - 0.02)
    )
    assert "SHELF_VERTICAL_GAP" not in _violation_codes(result)


def test_rack_with_small_shelf_gap_has_shelf_gap_violation() -> None:
    result = StorageSizingCalculator().calculate(
        _sizing_input(StorageMethod.RACK, gap_m=MIN_SHELF_VERTICAL_GAP_M - 0.02)
    )
    assert "SHELF_VERTICAL_GAP" in _violation_codes(result)


def _short_term_storage(name: str, items: list[ExplosiveItem]) -> StorageBuilding:
    return StorageBuilding(
        name=name,
        category=WarehouseCategory.EXPENDABLE,
        duration=WarehouseDuration.SHORT_TERM,
        location_type=LocationType.SURFACE,
        items=items,
    )


def test_short_term_initiating_devices_do_not_count_toward_mass_limit() -> None:
    si_mass_kg = MAX_SHORT_TERM_SINGLE_STORAGE_VM_KG
    storage = _short_term_storage(
        "Склад СИ",
        [
            ExplosiveItem(
                name="Электродетонаторы",
                group=CompatibilityGroup.S,
                mass_kg=si_mass_kg,
                si_count=10,
                is_initiating_device=True,
            ),
        ],
    )
    project = WarehouseProjectInput(name="Тест", storages=[storage])
    result = validate_short_term_limits(project)
    assert "SHORT_TERM_SINGLE_STORAGE_VM" not in [v.code for v in result.violations]
    assert "SHORT_TERM_TOTAL_VM" not in [v.code for v in result.violations]


def test_berm_with_non_positive_height_raises_value_error() -> None:
    data = BermDesignInput(
        storage_length_m=10.0,
        storage_width_m=8.0,
        eaves_height_m=2.0,
        crest_elevation_above_eaves_m=-2.5,
        soil_material=BermSoilMaterial.PLASTIC_CLAY_LOAM,
    )
    with pytest.raises(ValueError):
        calculate_berm_design(data)


def test_mutating_loaded_tables_does_not_affect_next_call() -> None:
    first = load_appendix11_tables()
    original_keys = set(first["uvv_damage_degrees"].keys())
    first["uvv_damage_degrees"].clear()
    second = load_appendix11_tables()
    assert set(second["uvv_damage_degrees"].keys()) == original_keys


def test_master_plan_dimension_text_marks_violation(tmp_path: Path) -> None:
    data = build_sample_note_data(35.0)
    output = tmp_path / "master_plan.dxf"
    export_master_plan_dxf(
        data.project,
        data.detonation_results,
        data.uvv_results,
        {record.storage_id: record.result for record in data.berm_records},
        output,
    )
    doc = ezdxf.readfile(output)
    texts = [entity.dxf.text for entity in doc.modelspace().query("DIMENSION")]
    texts += [entity.dxf.text for entity in doc.modelspace().query("MTEXT")]
    assert any("<" in text and "НАРУШЕНИЕ" in text for text in texts if text)


def test_note_shows_less_than_sign_for_violated_wall_clearance(tmp_path: Path) -> None:
    data = build_sample_note_data()
    record = data.sizing_records[0]
    broken_input = record.sizing_input.model_copy(update={"wall_clearance_m": 0.1})
    broken_record = type(record)(storage_id=record.storage_id, sizing_input=broken_input, result=record.result)
    output = tmp_path / "note.docx"
    export_explanatory_note_docx(
        data.project,
        [broken_record, *data.sizing_records[1:]],
        data.detonation_results,
        data.uvv_results,
        data.berm_records,
        data.lightning_records,
        output,
    )
    text = "\n".join(paragraph.text for paragraph in docx.Document(output).paragraphs)
    assert "отступ 0.10 м < 0.20 м" in text


def test_note_marks_missing_tnt_coefficient_as_not_set(tmp_path: Path) -> None:
    data = build_sample_note_data()
    storage = data.project.storages[0]
    storage.items[0] = storage.items[0].model_copy(update={"tnt_equivalent_coeff": None})
    output = tmp_path / "note.docx"
    export_explanatory_note_docx(
        data.project,
        data.sizing_records,
        data.detonation_results,
        data.uvv_results,
        data.berm_records,
        data.lightning_records,
        output,
    )
    document = docx.Document(output)
    cell_texts = [cell.text for table in document.tables for row in table.rows for cell in row.cells]
    assert "не задан" in cell_texts
    red_text = [
        run.text
        for paragraph in document.paragraphs
        for run in paragraph.runs
        if run.bold and run.font.color.rgb == RED
    ]
    assert any("не задан коэффициент K_тэ" in text for text in red_text)
