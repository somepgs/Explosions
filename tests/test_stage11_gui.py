"""Этап 11: интерфейс PySide6. Сессия проверяется без Qt, окна — на offscreen-платформе."""

import os
from pathlib import Path

import pytest

from explosions_core.domain import ProjectDefinition
from explosions_core.gui.labels import format_validation_error, enum_label
from explosions_core.gui.results_view import fmt, overall_status, STATUS_FAIL, STATUS_OK
from explosions_core.gui.session import (
    ProjectSession,
    ProjectSessionError,
    definition_from_dict,
    new_definition,
)
from explosions_core.domain import WarehouseDuration
from pydantic import ValidationError

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "demo_project.json"


def _demo_definition() -> ProjectDefinition:
    return ProjectDefinition.model_validate_json(EXAMPLE.read_text(encoding="utf-8"))


def test_new_definition_is_valid_and_has_template_storage() -> None:
    definition = new_definition()
    assert len(definition.project.storages) == 1
    assert definition.project.storages[0].storage_id == "S1"
    ProjectDefinition.model_validate(definition.model_dump())


def test_session_save_and_open_cyrillic_path(tmp_path: Path) -> None:
    session = ProjectSession(_demo_definition())
    target = tmp_path / "Проект склада.json"
    session.save(target)
    reopened = ProjectSession()
    reopened.open(target)
    assert reopened.definition == session.definition
    assert reopened.path == target
    assert reopened.dirty is False


def test_session_calculate_demo_is_compliant() -> None:
    session = ProjectSession(_demo_definition())
    result = session.calculate()
    assert result.is_compliant
    assert session.result is result


def test_session_export_requires_calculation(tmp_path: Path) -> None:
    session = ProjectSession(_demo_definition())
    with pytest.raises(ProjectSessionError):
        session.export(tmp_path)


def test_session_export_writes_files(tmp_path: Path) -> None:
    session = ProjectSession(_demo_definition())
    session.calculate()
    written = session.export(tmp_path, dxf=False, docx=True, json_result=True)
    names = {path.name for path in written}
    assert any(name.endswith(".docx") for name in names)
    assert any(name.endswith(".json") for name in names)
    assert all(path.exists() for path in written)


def test_schema_error_names_field_in_russian() -> None:
    data = _demo_definition().model_dump()
    data["project"]["storages"][0]["mass_kg"] = "много"
    with pytest.raises(ProjectSessionError) as info:
        definition_from_dict(data)
    text = str(info.value)
    assert text.startswith("Данные не соответствуют схеме проекта")
    assert "•" in text


def test_validation_error_text_uses_russian_field_names() -> None:
    data = _demo_definition().model_dump()
    data["project"]["storages"][0]["unknown_field"] = 1
    with pytest.raises(ValidationError) as info:
        ProjectDefinition.model_validate(data)
    text = format_validation_error(info.value)
    assert "неизвестное поле" in text
    assert "Хранилища" in text


def test_enum_label_is_russian() -> None:
    assert enum_label(WarehouseDuration.PERMANENT) == "постоянный"


def test_fmt_uses_decimal_comma() -> None:
    assert fmt(80.0) == "80,00"
    assert fmt(None) == "—"


def test_overall_status_for_compliant_demo() -> None:
    result = ProjectSession(_demo_definition()).calculate()
    status, text = overall_status(result)
    assert status in (STATUS_OK, "warn")
    assert text


def test_overall_status_fails_on_calculation_error() -> None:
    data = _demo_definition().model_dump()
    data["project"]["storages"][0]["items"][0]["detonation_class"] = None
    result = ProjectSession(definition_from_dict(data)).calculate()
    status, text = overall_status(result)
    assert status == STATUS_FAIL
    assert "ошибками" in text


def test_pipeline_error_is_issue_not_crash() -> None:
    data = _demo_definition().model_dump()
    data["project"]["storages"][0]["items"][0]["detonation_class"] = None
    definition = definition_from_dict(data)
    result = ProjectSession(definition).calculate()
    assert result.errors


# GUI-тесты: при отсутствии PySide6 пропускаются, остальной набор не затрагивается.
pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(["explosions-tests"])
    yield app


def test_project_form_round_trip_demo(qapp) -> None:
    from explosions_core.gui.steps import ProjectStep, TerritoryStep
    from explosions_core.gui.wizard_data import WizardData

    definition = _demo_definition()
    data = WizardData(definition)
    project_step = ProjectStep(data)
    territory_step = TerritoryStep(data)
    project_step.load()
    territory_step.load()
    assert project_step.form.data()["name"] == definition.project.name
    assert territory_step.form.data()["fence_height_m"] == pytest.approx(definition.project.fence_height_m)
    assert data.definition() == definition


def test_main_window_loads_demo_and_collects_definition(qapp) -> None:
    from explosions_core.gui.main_window import MainWindow

    session = ProjectSession(_demo_definition())
    window = MainWindow(session)
    collected = window._collect_definition()
    assert len(collected.project.storages) == len(session.definition.project.storages)
    assert collected.project.storages[0].name == session.definition.project.storages[0].name


class _SilentDialogs:
    """Фейковые окна: подтверждают расчет без показа модальных диалогов (в тестах окна не блокируются)."""

    def __init__(self) -> None:
        self.precheck_calls = 0
        self.summary_calls = 0
        self.errors: list[str] = []

    def ask_precheck(self, items):
        from explosions_core.gui.dialogs import CHOICE_CALCULATE

        self.precheck_calls += 1
        return CHOICE_CALCULATE, None

    def show_summary(self, result) -> None:
        self.summary_calls += 1

    def show_error(self, title: str, text: str) -> None:
        self.errors.append(text)


def test_main_window_calculation_fills_results(qapp) -> None:
    from explosions_core.gui.main_window import MainWindow

    session = ProjectSession(_demo_definition())
    dialogs = _SilentDialogs()
    window = MainWindow(session, dialogs=dialogs)
    assert window.calculate() is True
    assert dialogs.summary_calls == 1
    assert session.result is not None
    banner = window._results_page.banner_text()
    assert banner
    assert window._results_page.tab_titles()[0] == "Нарушения"


def test_plan_draws_one_rect_per_placed_storage(qapp) -> None:
    from explosions_core.gui.main_window import MainWindow

    session = ProjectSession(_demo_definition())
    window = MainWindow(session, dialogs=_SilentDialogs())
    window.calculate()
    view = window._plan_page.view
    placed = [s for s in session.definition.project.storages if s.x_m is not None and s.length_m is not None]
    assert view.rect_count() >= len(placed)


def test_main_window_saves_to_and_opens_from_database(qapp, tmp_path: Path) -> None:
    from explosions_core.gui.main_window import MainWindow
    from explosions_core.io.project_db import ProjectDatabase

    class _PickFirstDialogs(_SilentDialogs):
        def choose_project(self, records):
            return records[0].id

    database = ProjectDatabase(tmp_path / "projects.sqlite3")
    session = ProjectSession(_demo_definition(), database=database)
    window = MainWindow(session, dialogs=_PickFirstDialogs())
    assert window.save_to_database() is True
    assert session.project_id is not None

    session.new_project()
    assert window.open_from_database() is True
    assert session.project_id is not None
    assert session.definition.project.name == _demo_definition().project.name


def test_storage_page_add_and_remove(qapp) -> None:
    from explosions_core.gui.steps import StoragesStep
    from explosions_core.gui.wizard_data import WizardData

    data = WizardData()
    step = StoragesStep(data)
    step.load()
    step.add_storage()
    assert data.storage_count() == 1
    step.remove_storage()
    assert data.storages == []
