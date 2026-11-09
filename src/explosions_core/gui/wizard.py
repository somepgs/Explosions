"""Мастер из восьми шагов: порядок шагов, навигация и связь шага с разделом данных (без Qt).

Шаги не навязывают порядок: любой шаг открывается щелчком. Кнопки «Назад» и «Далее» просто
переходят к соседнему шагу. Раздел данных определяет, какие поля шага собираются в проект.
"""

from dataclasses import dataclass

from explosions_core.gui.help_texts import STEP_INSTRUCTIONS, STEP_TITLES
from explosions_core.gui.precheck import (
    STEP_CALCULATION,
    STEP_LIGHTNING,
    STEP_PLACEMENT,
    STEP_PROJECT,
    STEP_SIZING,
    STEP_STORAGES,
    STEP_TARGETS,
    STEP_TERRITORY,
)

FIRST_STEP = STEP_PROJECT
LAST_STEP = STEP_CALCULATION
PROJECTS_PAGE_INDEX = 0
PROJECTS_PAGE_TITLE = "Проекты"


@dataclass(frozen=True)
class WizardStep:
    number: int
    title: str
    instruction: str
    data_section: str


WIZARD_STEPS: tuple[WizardStep, ...] = (
    WizardStep(STEP_PROJECT, STEP_TITLES[STEP_PROJECT], STEP_INSTRUCTIONS[STEP_PROJECT], "project"),
    WizardStep(STEP_STORAGES, STEP_TITLES[STEP_STORAGES], STEP_INSTRUCTIONS[STEP_STORAGES], "storage_general"),
    WizardStep(STEP_SIZING, STEP_TITLES[STEP_SIZING], STEP_INSTRUCTIONS[STEP_SIZING], "sizing"),
    WizardStep(STEP_PLACEMENT, STEP_TITLES[STEP_PLACEMENT], STEP_INSTRUCTIONS[STEP_PLACEMENT], "placement"),
    WizardStep(STEP_LIGHTNING, STEP_TITLES[STEP_LIGHTNING], STEP_INSTRUCTIONS[STEP_LIGHTNING], "lightning"),
    WizardStep(STEP_TERRITORY, STEP_TITLES[STEP_TERRITORY], STEP_INSTRUCTIONS[STEP_TERRITORY], "territory"),
    WizardStep(STEP_TARGETS, STEP_TITLES[STEP_TARGETS], STEP_INSTRUCTIONS[STEP_TARGETS], "targets"),
    WizardStep(STEP_CALCULATION, STEP_TITLES[STEP_CALCULATION], STEP_INSTRUCTIONS[STEP_CALCULATION], "calculation"),
)

STEP_BY_NUMBER: dict[int, WizardStep] = {step.number: step for step in WIZARD_STEPS}


def navigation_titles() -> list[str]:
    """Пункты левой панели: сначала «Проекты» (список из базы), затем восемь шагов."""
    return [PROJECTS_PAGE_TITLE] + [step.title for step in WIZARD_STEPS]


def step_to_navigation_row(step: int) -> int:
    """Строка левой панели для номера шага (строка 0 — «Проекты»)."""
    if step not in STEP_BY_NUMBER:
        raise ValueError(f"Нет шага мастера с номером {step}")
    return step


def navigation_row_to_step(row: int) -> int | None:
    """Номер шага для строки левой панели; None для «Проекты» и вне диапазона."""
    if row <= PROJECTS_PAGE_INDEX or row > LAST_STEP:
        return None
    return row


def next_step(step: int) -> int | None:
    return step + 1 if step < LAST_STEP else None


def previous_step(step: int) -> int | None:
    return step - 1 if step > FIRST_STEP else None
