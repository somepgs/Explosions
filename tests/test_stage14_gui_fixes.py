"""Этап 14 (Qt): результаты с текстовыми значениями нарушений и форма фактической планировки на шаге 3.

Модуль пропускается без PySide6; проверки без Qt — в `test_stage14_review_fixes.py`.
"""

import os

import pytest

from explosions_core.domain import ProjectDefinition
from explosions_core.gui.session import ProjectSession
from tests.fixtures.sample_project import build_sample_project_definition

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(["explosions-tests"])
    yield app


class _SilentDialogs:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def ask_precheck(self, items):
        from explosions_core.gui.dialogs import CHOICE_CALCULATE

        return CHOICE_CALCULATE, None

    def show_summary(self, result) -> None:
        pass

    def show_error(self, title: str, text: str) -> None:
        self.errors.append(text)


def _without_lightning(definition: ProjectDefinition) -> ProjectDefinition:
    designs = [design.model_copy(update={"lightning": None}) for design in definition.storage_designs]
    return definition.model_copy(update={"storage_designs": designs})


def test_results_page_shows_text_violation_values(qapp) -> None:
    from explosions_core.gui.main_window import MainWindow

    session = ProjectSession(_without_lightning(build_sample_project_definition()))
    window = MainWindow(session, dialogs=_SilentDialogs())

    assert window.calculate() is True
    table = window._results_page.table("Нарушения")
    codes = [table.item(row, 0).text() for row in range(table.rowCount())]
    assert codes.count("LIGHTNING_REQUIRED") == 2
    row = codes.index("LIGHTNING_REQUIRED")
    assert table.item(row, 2).text() == "не задана"


def test_sizing_step_edits_actual_internal_layout(qapp) -> None:
    from explosions_core.gui.steps import SizingStep
    from explosions_core.gui.wizard_data import WizardData

    data = WizardData(build_sample_project_definition())
    step = SizingStep(data)
    step.load()

    form = next(form for form in step.storage_forms() if form.has_field("layout"))
    group = form.child("layout")
    group.setChecked(True)
    group.form.set_data({"storage_method": "stack", "packaging": "bag", "wall_clearance_m": 0.1})
    step._on_storage_changed()

    layout = data.definition().project.storages[0].layout
    assert layout is not None
    assert layout.wall_clearance_m == pytest.approx(0.1)
    assert any("LAYOUT_WALL_CLEARANCE" in line or "от стены" in line for line in step.preview_lines(0))
