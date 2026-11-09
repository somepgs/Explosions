"""Окна предупреждений и пояснений интерфейса (PySide6).

Все модальные окна вынесены в `DialogService`: в тестах он подменяется фейком, чтобы не блокировать offscreen-запуск.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from explosions_core.domain import ProjectCalculationResult
from explosions_core.gui.explanations import result_summary_lines
from explosions_core.gui.precheck import ReadinessItem, readiness_summary
from explosions_core.io.project_db import ProjectRecord

APP_TITLE = "Склад ВМ: расчетное ядро"
LEVEL_PREFIX = {"error": "ОШИБКА", "warning": "Внимание", "info": "Подсказка"}

CHOICE_CORRECT = "correct"
CHOICE_CALCULATE = "calculate"
CHOICE_CANCEL = "cancel"


class PrecheckDialog(QDialog):
    """Список незаполненных данных с подсказкой, куда перейти. Выбор пользователя возвращается в `choice`."""

    def __init__(self, items: list[ReadinessItem], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Проверка данных перед расчетом")
        self.setMinimumWidth(640)
        self.choice = CHOICE_CANCEL
        self._items = items
        errors, warnings = readiness_summary(items)
        header = QLabel(self._header_text(errors, warnings), self)
        header.setWordWrap(True)
        self._list = QListWidget(self)
        self._list.setWordWrap(True)
        for item in items:
            widget_item = QListWidgetItem(_item_text(item))
            widget_item.setToolTip(item.hint)
            self._list.addItem(widget_item)
        self.target_step: int | None = None
        self._list.itemDoubleClicked.connect(self._go_to_selected)
        self._buttons = QDialogButtonBox(self)
        self._correct = self._buttons.addButton("Исправить данные", QDialogButtonBox.ButtonRole.AcceptRole)
        self._calculate = self._buttons.addButton("Рассчитать все равно", QDialogButtonBox.ButtonRole.ActionRole)
        self._cancel = self._buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        self._correct.clicked.connect(self._choose_correct)
        self._calculate.clicked.connect(self._choose_calculate)
        self._cancel.clicked.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(header)
        layout.addWidget(self._list)
        layout.addWidget(QLabel("Двойной щелчок по строке — переход к шагу, где это заполняется.", self))
        layout.addWidget(self._buttons)
        if errors:
            self._calculate.setEnabled(False)
            self._calculate.setToolTip("Сначала исправьте ошибки: без них расчет не выполнится")

    @staticmethod
    def _header_text(errors: int, warnings: int) -> str:
        if errors:
            return (
                f"Расчет невозможен: не заполнено {errors} обязательных данных. "
                f"Предупреждений: {warnings}. Исправьте ошибки и откройте расчет снова."
            )
        return (
            f"Расчет можно выполнить, но данных не хватает для полной проверки. Предупреждений: {warnings}. "
            "Рекомендуется заполнить их до выпуска документов."
        )

    def _choose_correct(self) -> None:
        self.choice = CHOICE_CORRECT
        self.accept()

    def _choose_calculate(self) -> None:
        self.choice = CHOICE_CALCULATE
        self.accept()

    def _go_to_selected(self, *_args) -> None:
        row = self._list.currentRow()
        if 0 <= row < len(self._items):
            self.target_step = self._items[row].step
            self.choice = CHOICE_CORRECT
            self.accept()


class ResultSummaryDialog(QDialog):
    """Сводка после расчета: статус и первые нарушения с пояснениями."""

    def __init__(self, result: ProjectCalculationResult, lines: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Итоги расчета")
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        for line in lines:
            label = QLabel(line, self)
            label.setWordWrap(True)
            layout.addWidget(label)
        details = QListWidget(self)
        for violation in result.all_violations[:20]:
            details.addItem(f"[{violation.clause}] {violation.description}")
        if result.all_violations:
            layout.addWidget(QLabel("Первые нарушения (полный список на вкладке «Результаты»):", self))
            layout.addWidget(details)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, self)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class ProjectChooserDialog(QDialog):
    """Список проектов из базы данных: выбрать и открыть двойным щелчком или кнопкой «Открыть»."""

    def __init__(self, records: list[ProjectRecord], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Проекты в базе данных")
        self.setMinimumWidth(480)
        self.selected_id: int | None = None
        self._ids: list[int] = [record.id for record in records]
        self._list = QListWidget(self)
        for record in records:
            self._list.addItem(f"{record.name}    (изменен: {record.updated_at})")
        if records:
            self._list.setCurrentRow(0)
        self._list.itemDoubleClicked.connect(lambda *_: self._accept_current())
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self._accept_current)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Выберите проект для открытия:", self))
        layout.addWidget(self._list)
        layout.addWidget(buttons)

    def _accept_current(self) -> None:
        row = self._list.currentRow()
        if 0 <= row < len(self._ids):
            self.selected_id = self._ids[row]
            self.accept()


class DialogService:
    """Все пользовательские окна в одном месте. Тесты подменяют класс фейком."""

    def __init__(self, parent: QWidget) -> None:
        self._parent = parent

    def show_error(self, title: str, text: str) -> None:
        box = QMessageBox(QMessageBox.Icon.Warning, title, text, QMessageBox.StandardButton.Ok, self._parent)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.exec()

    def show_info(self, title: str, text: str) -> None:
        box = QMessageBox(QMessageBox.Icon.Information, title, text, QMessageBox.StandardButton.Ok, self._parent)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.exec()

    def confirm(self, title: str, text: str) -> bool:
        box = QMessageBox(
            QMessageBox.Icon.Question,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            self._parent,
        )
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        return box.exec() == QMessageBox.StandardButton.Yes

    def ask_precheck(self, items: list[ReadinessItem]) -> tuple[str, int | None]:
        dialog = PrecheckDialog(items, self._parent)
        dialog.exec()
        return dialog.choice, dialog.target_step

    def show_summary(self, result: ProjectCalculationResult) -> None:
        dialog = ResultSummaryDialog(result, result_summary_lines(result), self._parent)
        dialog.exec()

    def choose_project(self, records: list[ProjectRecord]) -> int | None:
        dialog = ProjectChooserDialog(records, self._parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selected_id
        return None


def _item_text(item: ReadinessItem) -> str:
    prefix = LEVEL_PREFIX[item.level]
    where = f" [{item.storage}]" if item.storage else ""
    return f"{prefix}{where}: {item.message}\n    Что сделать: {item.hint}"
