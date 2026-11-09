import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from explosions_core.calc.safe_distances import SafeDistanceEngine
from explosions_core.cli import EXIT_INPUT_ERROR, EXIT_NONCOMPLIANT, EXIT_OK, main
from explosions_core.domain import (
    CompatibilityGroup,
    ExplosiveItem,
    ProjectDefinition,
)
from explosions_core.io.project_file import ProjectFileError, load_project_file, save_project_file
from explosions_core.pipeline import calculate_project
from tests.fixtures.sample_project import (
    SAMPLE_DEFAULT_CLEAR_DISTANCE_M,
    build_sample_project_definition,
    build_sample_project_result,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_PROJECT_PATH = REPO_ROOT / "examples" / "demo_project.json"


def test_pipeline_fills_building_size_from_sizing() -> None:
    result = build_sample_project_result()
    for storage in result.project.storages:
        assert storage.length_m is not None and storage.width_m is not None
    assert len(result.sizing_records) == 2
    assert len(result.berm_records) == 2
    assert len(result.lightning_records) == 2


def test_detonation_and_uvv_match_direct_engine_calls() -> None:
    result = build_sample_project_result()
    engine = SafeDistanceEngine()
    direct_pairs = engine.detonation_matrix(result.project.storages)
    assert len(result.detonation_results) == len(direct_pairs) == 1
    for pipeline_pair, direct_pair in zip(result.detonation_results, direct_pairs):
        assert pipeline_pair.governing_required_r_d_m == pytest.approx(direct_pair.governing_required_r_d_m)
        assert pipeline_pair.actual_clear_distance_m == pytest.approx(direct_pair.actual_clear_distance_m)

    direct_uvv = engine.uvv_matrix(result.project.storages, result.project.external_targets)
    assert len(result.uvv_results) == len(direct_uvv) == 4
    for pipeline_uvv, direct in zip(result.uvv_results, direct_uvv):
        assert pipeline_uvv.required_distance_m == pytest.approx(direct.required_distance_m)


def test_sample_numbers_match_reference_values() -> None:
    result = build_sample_project_result()
    pair = result.detonation_results[0]
    assert f"{pair.governing_required_r_d_m:.2f}" == "8.50"
    # S1: катящаяся сфера СП РК уровня I (D = 20 м), h = 14.5 м: R0 = sqrt(14.5 * 25.5), на коньке h' = 8: sqrt(8 * 32) = 16
    mast_m1 = result.lightning_records[0].result.mast_results[0]
    assert f"{mast_m1['r0_ground_m']:.2f}" == "19.23"
    assert f"{mast_m1['rx_at_ridge_m']:.2f}" == "16.00"
    # S2: табл. 3.4 СО 153, P = 0.999, h = 25 м: h0 = 17.5, r0 = 15.0, rx(6.5) = 15 * 11 / 17.5
    mast_m3 = result.lightning_records[1].result.mast_results[0]
    assert f"{mast_m3['h0_m']:.2f}" == "17.50"
    assert f"{mast_m3['r0_ground_m']:.2f}" == "15.00"
    assert f"{mast_m3['rx_at_ridge_m']:.2f}" == "9.43"
    assert result.is_compliant


def test_violation_is_reported_when_storages_are_too_close() -> None:
    result = build_sample_project_result(clear_distance_m=5.0)
    codes = {violation.code for violation in result.all_violations}
    assert "DETONATION_TRANSFER_DISTANCE" in codes
    assert not result.is_compliant


def test_missing_detonation_class_is_isolated_as_error() -> None:
    definition = build_sample_project_definition()
    storages = list(definition.project.storages)
    broken_item = ExplosiveItem(
        name="Партия без класса по таблице 4",
        group=CompatibilityGroup.D,
        mass_kg=1000.0,
        detonation_class=None,
    )
    storages[1] = storages[1].model_copy(update={"items": [broken_item]})
    broken = definition.model_copy(update={"project": definition.project.model_copy(update={"storages": storages})})

    result = calculate_project(broken)

    assert any(issue.severity == "error" and issue.module == "detonation" for issue in result.issues)
    assert not any(issue.module == "uvv" for issue in result.issues)
    assert len(result.sizing_records) == 2
    assert result.detonation_results == []
    assert len(result.uvv_results) == 4
    assert not result.is_compliant


def test_unknown_design_storage_is_error() -> None:
    definition = build_sample_project_definition()
    extra = definition.storage_designs[0].model_copy(update={"storage_id": "NOPE"})
    broken = definition.model_copy(update={"storage_designs": [*definition.storage_designs, extra]})
    result = calculate_project(broken)
    assert any(issue.module == "design" and issue.object_id == "NOPE" for issue in result.issues)


def test_duplicate_storage_ids_raise_value_error() -> None:
    definition = build_sample_project_definition()
    storages = list(definition.project.storages)
    storages[1] = storages[1].model_copy(update={"storage_id": "S1"})
    broken = definition.model_copy(update={"project": definition.project.model_copy(update={"storages": storages})})
    with pytest.raises(ValueError):
        calculate_project(broken)


def test_project_round_trip_preserves_cyrillic(tmp_path: Path) -> None:
    definition = build_sample_project_definition()
    path = tmp_path / "project.json"
    save_project_file(definition, path)
    text = path.read_text(encoding="utf-8")
    assert "Демонстрационный" in text
    loaded = load_project_file(path)
    assert loaded == definition


def test_unknown_field_is_rejected(tmp_path: Path) -> None:
    payload = json.loads(build_sample_project_definition().model_dump_json())
    payload["project"]["fence_hieght_m"] = 2.0
    path = tmp_path / "typo.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ProjectFileError) as info:
        load_project_file(path)
    assert "fence_hieght_m" in str(info.value)


def test_invalid_json_raises_project_file_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ProjectFileError):
        load_project_file(path)


def test_missing_file_raises_project_file_error(tmp_path: Path) -> None:
    with pytest.raises(ProjectFileError):
        load_project_file(tmp_path / "absent.json")


def test_schema_version_is_checked() -> None:
    payload = json.loads(build_sample_project_definition().model_dump_json())
    payload["schema_version"] = "2"
    with pytest.raises(ValidationError):
        ProjectDefinition.model_validate(payload)


def test_cli_calc_writes_all_outputs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project_path = tmp_path / "project.json"
    save_project_file(build_sample_project_definition(), project_path)
    out_dir = tmp_path / "out"

    code = main(["calc", str(project_path), "--dxf", "--docx", "--json", "--out", str(out_dir)])

    assert code == EXIT_OK
    assert (out_dir / "master_plan_safety_zones.dxf").is_file()
    assert (out_dir / "storage_detail_S1.dxf").is_file()
    assert (out_dir / "explanatory_note.docx").is_file()
    assert (out_dir / "calculation_result.json").is_file()
    assert "Итог: соответствует нормативам" in capsys.readouterr().out


def test_cli_calc_returns_noncompliant_code(tmp_path: Path) -> None:
    definition = build_sample_project_definition(clear_distance_m=5.0)
    project_path = tmp_path / "close.json"
    save_project_file(definition, project_path)
    assert main(["calc", str(project_path)]) == EXIT_NONCOMPLIANT


def test_cli_validate_accepts_valid_file(tmp_path: Path) -> None:
    project_path = tmp_path / "project.json"
    save_project_file(build_sample_project_definition(), project_path)
    assert main(["validate", str(project_path)]) == EXIT_OK


def test_cli_missing_file_returns_input_error(tmp_path: Path) -> None:
    assert main(["calc", str(tmp_path / "absent.json")]) == EXIT_INPUT_ERROR


def test_demo_project_file_loads_and_calculates() -> None:
    assert DEMO_PROJECT_PATH.is_file()
    definition = load_project_file(DEMO_PROJECT_PATH)
    result = calculate_project(definition)
    assert len(result.sizing_records) == 2
    assert result.is_compliant


def test_sample_default_distance_keeps_storages_separate() -> None:
    result = build_sample_project_result(clear_distance_m=SAMPLE_DEFAULT_CLEAR_DISTANCE_M)
    assert result.detonation_results[0].actual_clear_distance_m == pytest.approx(SAMPLE_DEFAULT_CLEAR_DISTANCE_M)
