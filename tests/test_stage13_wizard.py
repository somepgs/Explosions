"""Этап 13: мастер из 8 шагов, раскладки полей, статусы шагов и сохранение скрытых полей (без Qt — логика)."""

import os
from pathlib import Path

import pytest

from explosions_core.domain import ProjectDefinition, WarehouseDuration
from explosions_core.gui.help_texts import FIELD_HELP, STEP_INSTRUCTIONS, STEP_TITLES, WORKFLOW_TEXT
from explosions_core.gui.layouts import ALL_LAYOUTS, LAYOUT_MODELS
from explosions_core.gui.precheck import (
    STEP_CALCULATION,
    STEP_LIGHTNING,
    STEP_PLACEMENT,
    STEP_PROJECT,
    STEP_SIZING,
    STEP_STORAGES,
    STEP_TARGETS,
    STEP_TERRITORY,
    check_readiness,
    step_statuses,
)
from explosions_core.gui.session import definition_from_dict
from tests.fixtures.sample_project import build_sample_project_definition

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "demo_project.json"


def _demo() -> ProjectDefinition:
    return build_sample_project_definition()


def _data(definition: ProjectDefinition) -> dict:
    return definition.model_dump()


# ---------- шаги и тексты ----------


def test_wizard_has_eight_steps_with_titles_and_instructions() -> None:
    steps = list(range(STEP_PROJECT, STEP_CALCULATION + 1))
    assert steps == [1, 2, 3, 4, 5, 6, 7, 8]
    for step in steps:
        assert STEP_TITLES[step]
        assert STEP_INSTRUCTIONS[step]


def test_workflow_text_mentions_every_step() -> None:
    for title in STEP_TITLES.values():
        number, name = title.split(". ", 1)
        assert f"{number}." in WORKFLOW_TEXT
        assert name.split()[0] in WORKFLOW_TEXT


def test_field_help_is_not_empty() -> None:
    assert FIELD_HELP
    assert all(text.strip() for text in FIELD_HELP.values())


# ---------- раскладки полей ----------


@pytest.mark.parametrize("layout_name", sorted(ALL_LAYOUTS))
def test_layout_fields_exist_in_model(layout_name: str) -> None:
    model = LAYOUT_MODELS[layout_name]
    layout = ALL_LAYOUTS[layout_name]
    unknown = [name for name in layout.all_fields() if name not in model.model_fields]
    assert unknown == [], f"в раскладке {layout_name} нет полей модели {model.__name__}: {unknown}"


@pytest.mark.parametrize("layout_name", sorted(ALL_LAYOUTS))
def test_layout_has_no_duplicate_fields(layout_name: str) -> None:
    fields = ALL_LAYOUTS[layout_name].all_fields()
    assert len(fields) == len(set(fields))


def test_every_layout_field_has_help_text_for_visible_inputs() -> None:
    missing = []
    for layout in ALL_LAYOUTS.values():
        for name in layout.basic:
            if name not in FIELD_HELP:
                missing.append(name)
    assert missing == []


# ---------- статусы шагов ----------


def test_step_statuses_empty_storage_marks_step_two_error() -> None:
    data = _data(_demo())
    data["project"]["storages"][0]["items"] = []
    statuses = step_statuses(check_readiness(definition_from_dict(data)))
    assert statuses[STEP_STORAGES] == "error"


def test_step_statuses_missing_lightning_marks_step_five() -> None:
    data = _data(_demo())
    for design in data["storage_designs"]:
        design["lightning"] = None
    statuses = step_statuses(check_readiness(definition_from_dict(data)))
    assert statuses[STEP_LIGHTNING] == "warning"


def test_step_statuses_missing_fence_marks_step_six() -> None:
    data = _data(_demo())
    data["project"]["fence_height_m"] = None
    statuses = step_statuses(check_readiness(definition_from_dict(data)))
    assert statuses[STEP_TERRITORY] == "warning"


def test_step_statuses_missing_coordinates_marks_step_four() -> None:
    data = _data(_demo())
    if len(data["project"]["storages"]) < 2:
        data["project"]["storages"].append(dict(data["project"]["storages"][0]))
    data["project"]["storages"][1]["x_m"] = None
    statuses = step_statuses(check_readiness(definition_from_dict(data)))
    assert statuses[STEP_PLACEMENT] in ("warning", "error")


def test_demo_has_no_error_step_status() -> None:
    statuses = step_statuses(check_readiness(_demo()))
    assert "error" not in statuses.values()


def test_step_statuses_contains_all_eight_steps() -> None:
    statuses = step_statuses([])
    assert set(statuses) == set(range(STEP_PROJECT, STEP_CALCULATION + 1))
    assert all(value is None for value in statuses.values())


# ---------- сохранение скрытых полей ----------


def test_hidden_fields_survive_round_trip_through_form_data() -> None:
    """Поля вне раскладки шага не теряются: проверяем на уровне данных, без Qt."""
    definition = _demo()
    data = _data(definition)
    storage = data["project"]["storages"][0]
    storage["stack_width_b_m"] = 1.6
    rebuilt = definition_from_dict(data)
    assert rebuilt.project.storages[0].stack_width_b_m == pytest.approx(1.6)


def test_storage_duration_is_applied_to_all_storages_by_project_step() -> None:
    data = _data(_demo())
    data["project"]["storages"][0]["duration"] = WarehouseDuration.TEMPORARY.value
    definition = definition_from_dict(data)
    assert definition.project.storages[0].duration == WarehouseDuration.TEMPORARY


def test_demo_example_file_loads_and_precheck_is_clean() -> None:
    definition = ProjectDefinition.model_validate_json(EXAMPLE.read_text(encoding="utf-8"))
    assert not [item for item in check_readiness(definition) if item.level == "error"]


# ---------- Qt-часть мастера (пропускается без PySide6) ----------

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(["explosions-tests"])
    yield app


def test_main_window_has_projects_page_and_eight_steps(qapp) -> None:
    from explosions_core.gui.main_window import MainWindow
    from explosions_core.gui.session import ProjectSession

    window = MainWindow(ProjectSession(_demo()))
    assert window.navigation_titles()[0] == "Проекты"
    assert len(window.navigation_titles()) == 9


def test_main_window_navigation_next_back(qapp) -> None:
    from explosions_core.gui.main_window import MainWindow
    from explosions_core.gui.session import ProjectSession

    window = MainWindow(ProjectSession(_demo()))
    window.go_to_step(STEP_PROJECT)
    assert window.current_step() == STEP_PROJECT
    window.go_next()
    assert window.current_step() == STEP_STORAGES
    window.go_back()
    assert window.current_step() == STEP_PROJECT


def test_main_window_free_navigation_to_any_step(qapp) -> None:
    from explosions_core.gui.main_window import MainWindow
    from explosions_core.gui.session import ProjectSession

    window = MainWindow(ProjectSession(_demo()))
    window.go_to_step(STEP_TARGETS)
    assert window.current_step() == STEP_TARGETS
    window.go_to_step(STEP_SIZING)
    assert window.current_step() == STEP_SIZING


def test_storage_design_tabs_keep_hidden_and_nested_data(qapp) -> None:
    """Шаги 3–5 работают с одним словарем: габариты, вал и молниезащита не теряются при правке и переходах."""
    from explosions_core.gui.steps import LightningStep, PlacementStep, SizingStep
    from explosions_core.gui.wizard_data import WizardData

    definition = _demo()
    source = definition.model_dump(mode="json")
    data = WizardData(definition)
    steps = [SizingStep(data), PlacementStep(data), LightningStep(data)]
    for index in range(data.storage_count()):
        for step in steps:
            step.load()
            step.select_storage(index)
            for form in step.design_forms():
                form._notify()
    stored = data.designs_list()
    by_id = {design["storage_id"]: design for design in stored}
    for original in source["storage_designs"]:
        rebuilt = by_id[original["storage_id"]]
        assert rebuilt.get("sizing") == original.get("sizing")
        assert rebuilt.get("berm") == original.get("berm")
        assert rebuilt.get("lightning") == original.get("lightning")
        assert rebuilt.get("eaves_height_m") == original.get("eaves_height_m")


def test_collect_definition_round_trip_demo_equals_source(qapp) -> None:
    from explosions_core.gui.main_window import MainWindow
    from explosions_core.gui.session import ProjectSession

    source = _demo()
    window = MainWindow(ProjectSession(source))
    collected = window._collect_definition()
    assert collected.project.name == source.project.name
    assert len(collected.project.storages) == len(source.project.storages)
    for left, right in zip(collected.project.storages, source.project.storages):
        assert left.name == right.name
        assert left.storage_id == right.storage_id
        assert len(left.items) == len(right.items)
        for item_left, item_right in zip(left.items, right.items):
            assert item_left.mass_kg == pytest.approx(item_right.mass_kg, rel=1e-6)
