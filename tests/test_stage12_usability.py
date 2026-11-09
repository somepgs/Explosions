"""Этап 12: база данных SQLite, проверка готовности, пояснения к нарушениям, навигация мастера без Qt-зависимости."""

import re
from pathlib import Path

import pytest

from explosions_core.domain import NormativeViolation, ProjectDefinition
from explosions_core.gui.explanations import VIOLATION_EXPLANATIONS, explain_violation, result_summary_lines
from explosions_core.gui.precheck import check_readiness, has_blocking_errors, readiness_summary
from explosions_core.gui.session import ProjectSession, ProjectSessionError, definition_from_dict, new_definition
from explosions_core.io.project_db import ProjectDatabase, ProjectDatabaseError
from explosions_core.pipeline import calculate_project
from tests.fixtures.sample_project import build_sample_project_definition

SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "explosions_core"


def _demo() -> ProjectDefinition:
    return build_sample_project_definition()


def _data(definition: ProjectDefinition) -> dict:
    return definition.model_dump()


# ---------- база данных ----------


def test_database_creates_file_and_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "projects.sqlite3"
    ProjectDatabase(db_path)
    assert db_path.exists()


def test_database_round_trip_cyrillic_path(tmp_path: Path) -> None:
    folder = tmp_path / "Склад Ивановых"
    db = ProjectDatabase(folder / "проекты.sqlite3")
    definition = _demo()
    project_id = db.create_project(definition)
    loaded = db.load_project(project_id)
    assert loaded == definition


def test_database_list_save_duplicate_delete(tmp_path: Path) -> None:
    db = ProjectDatabase(tmp_path / "projects.sqlite3")
    definition = _demo()
    first = db.create_project(definition)
    names = [record.name for record in db.list_projects()]
    assert definition.project.name in names

    changed = definition.model_copy(update={"project": definition.project.model_copy(update={"name": "Новое имя"})})
    db.save_project(first, changed)
    assert db.load_project(first).project.name == "Новое имя"

    copy_id = db.duplicate_project(first, "Копия")
    assert db.load_project(copy_id).project.name == "Копия"

    db.delete_project(copy_id)
    with pytest.raises(ProjectDatabaseError):
        db.load_project(copy_id)


def test_database_missing_project_raises(tmp_path: Path) -> None:
    db = ProjectDatabase(tmp_path / "projects.sqlite3")
    with pytest.raises(ProjectDatabaseError):
        db.load_project(9999)
    with pytest.raises(ProjectDatabaseError):
        db.save_project(9999, _demo())


def test_database_keeps_calculation_history_and_cascade_delete(tmp_path: Path) -> None:
    db = ProjectDatabase(tmp_path / "projects.sqlite3")
    definition = _demo()
    project_id = db.create_project(definition)
    result = calculate_project(definition)
    db.add_calculation(project_id, result)
    db.add_calculation(project_id, result)
    history = db.list_calculations(project_id)
    assert len(history) == 2
    assert history[0].is_compliant == result.is_compliant
    assert history[0].violations_count == len(result.all_violations)

    db.delete_project(project_id)
    assert db.list_calculations(project_id) == []


def test_database_backup_is_readable(tmp_path: Path) -> None:
    db = ProjectDatabase(tmp_path / "projects.sqlite3")
    project_id = db.create_project(_demo())
    copy = db.backup(tmp_path / "backup" / "copy.sqlite3")
    assert copy.exists()
    assert ProjectDatabase(copy).load_project(project_id) == _demo()


def test_database_corrupt_file_raises(tmp_path: Path) -> None:
    broken = tmp_path / "projects.sqlite3"
    broken.write_bytes(b"this is not a sqlite database at all" * 50)
    with pytest.raises(ProjectDatabaseError):
        ProjectDatabase(broken)


# ---------- сессия с базой ----------


def test_session_saves_and_reopens_from_database(tmp_path: Path) -> None:
    db = ProjectDatabase(tmp_path / "projects.sqlite3")
    session = ProjectSession(_demo(), database=db)
    project_id = session.save_to_database()
    assert session.project_id == project_id
    session.calculate()
    assert len(db.list_calculations(project_id)) == 1

    reopened = ProjectSession(database=db)
    reopened.open_from_database(project_id)
    assert reopened.definition == _demo()
    assert reopened.project_id == project_id
    assert reopened.dirty is False


def test_session_without_database_raises_clear_error() -> None:
    session = ProjectSession(_demo())
    with pytest.raises(ProjectSessionError):
        session.save_to_database()


# ---------- проверка готовности ----------


def test_precheck_demo_has_no_blocking_errors() -> None:
    items = check_readiness(_demo())
    assert not has_blocking_errors(items)


def test_precheck_empty_project_reports_no_storages() -> None:
    definition = new_definition()
    data = _data(definition)
    data["project"]["storages"] = []
    items = check_readiness(definition_from_dict(data))
    assert any("нет ни одного хранилища" in item.message for item in items)
    assert has_blocking_errors(items)


def test_precheck_storage_without_explosives_is_error() -> None:
    data = _data(_demo())
    data["project"]["storages"][0]["items"] = []
    items = check_readiness(definition_from_dict(data))
    assert any("не указаны взрывчатые материалы" in item.message and item.level == "error" for item in items)


def test_precheck_missing_detonation_class_is_warning_with_step() -> None:
    data = _data(_demo())
    data["project"]["storages"][0]["items"][0]["detonation_class"] = None
    items = check_readiness(definition_from_dict(data))
    matched = [item for item in items if "класс по таблице 4" in item.message]
    assert matched
    assert matched[0].level == "warning"
    assert matched[0].step == 2
    assert matched[0].hint


def test_precheck_duplicate_storage_ids_is_error() -> None:
    data = _data(_demo())
    storages = data["project"]["storages"]
    if len(storages) < 2:
        storages.append(dict(storages[0]))
    storages[1]["storage_id"] = storages[0]["storage_id"]
    items = check_readiness(definition_from_dict(data))
    assert any("одинаковым обозначением" in item.message for item in items)


def test_precheck_missing_lightning_for_permanent_storage_is_warning() -> None:
    data = _data(_demo())
    for design in data["storage_designs"]:
        design["lightning"] = None
    items = check_readiness(definition_from_dict(data))
    assert any("молниезащиты" in item.message and item.level == "warning" for item in items)


def test_precheck_berm_without_flag_is_warning() -> None:
    data = _data(_demo())
    data["project"]["storages"][0]["is_bermed"] = False
    items = check_readiness(definition_from_dict(data))
    assert any("не отмечено как обвалованное" in item.message for item in items)


def test_precheck_mass_mismatch_is_warning() -> None:
    data = _data(_demo())
    design = next(d for d in data["storage_designs"] if d.get("sizing"))
    design["sizing"]["total_net_explosive_mass_kg"] = design["sizing"]["total_net_explosive_mass_kg"] + 1000.0
    items = check_readiness(definition_from_dict(data))
    assert any("не равна сумме партий" in item.message for item in items)


def test_readiness_summary_counts_levels() -> None:
    data = _data(_demo())
    data["project"]["storages"][0]["items"] = []
    items = check_readiness(definition_from_dict(data))
    errors, warnings = readiness_summary(items)
    assert errors == sum(1 for item in items if item.level == "error")
    assert warnings == sum(1 for item in items if item.level == "warning")
    assert errors >= 1


# ---------- пояснения ----------


def _source_violation_codes() -> set[str]:
    codes: set[str] = set()
    pattern = re.compile(r'code\s*=\s*"([A-Z][A-Z0-9_]+)"')
    for path in SRC_ROOT.rglob("*.py"):
        if "gui" in path.parts:
            continue
        codes.update(pattern.findall(path.read_text(encoding="utf-8")))
    return codes


def test_every_source_violation_code_has_explanation() -> None:
    codes = _source_violation_codes()
    assert codes, "коды нарушений не найдены в исходниках"
    missing = sorted(code for code in codes if code not in VIOLATION_EXPLANATIONS)
    assert missing == []


def test_explain_violation_returns_title_and_action_for_known_code() -> None:
    violation = NormativeViolation(
        code="WALL_CLEARANCE",
        clause="п. 579",
        description="Отступ",
        actual_value=0.1,
        required_value=0.2,
    )
    explanation = explain_violation(violation)
    assert explanation.title
    assert explanation.action


def test_explain_violation_fallback_for_unknown_code() -> None:
    violation = NormativeViolation(
        code="UNKNOWN_CODE_X",
        clause="п. 1",
        description="x",
        actual_value=0.0,
        required_value=1.0,
    )
    assert explain_violation(violation).title == "Нарушение нормы"


def test_result_summary_lines_for_compliant_demo() -> None:
    lines = result_summary_lines(calculate_project(_demo()))
    assert lines


def test_result_summary_reports_violations() -> None:
    data = _data(_demo())
    storages = data["project"]["storages"]
    if len(storages) >= 2:
        storages[1]["x_m"] = storages[0]["x_m"] + 1.0
    result = calculate_project(definition_from_dict(data))
    lines = result_summary_lines(result)
    assert lines
    if result.all_violations:
        assert any("нарушений" in line for line in lines)
