"""Содержимое восьми шагов мастера (PySide6).

Каждый шаг работает с общим `WizardData`: `load()` читает свои поля при показе шага, изменения в формах
сразу записываются обратно только по полям этого шага. Шаги 2–5 показывают слева список хранилищ,
справа — поля шага для выбранного хранилища и панель промежуточного результата.
"""

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from explosions_core.domain import (
    CalculationSettings,
    ExternalProtectedObject,
    ProjectCalculationResult,
    StorageBuilding,
    StorageDesignInput,
    WarehouseDuration,
    WarehouseProjectInput,
)
from explosions_core.gui.forms import ModelForm, ModelTable
from explosions_core.gui.labels import enum_choices
from explosions_core.gui.layouts import (
    BUILDING_PLACEMENT_LAYOUT,
    LIGHTNING_STEP_LAYOUT,
    PLACEMENT_LAYOUT,
    PROJECT_LAYOUT,
    SETTINGS_LAYOUT,
    SIZING_STEP_LAYOUT,
    STORAGE_GENERAL_LAYOUT,
    TERRITORY_LAYOUT,
)
from explosions_core.gui.pages import PlanPage, ResultsPage
from explosions_core.gui.plan_view import PlanView
from explosions_core.gui.precheck import ReadinessItem
from explosions_core.gui.previews import (
    lightning_preview_lines,
    placement_preview_lines,
    sizing_preview_lines,
    storage_check_lines,
)
from explosions_core.gui.widgets import CollapsibleSection
from explosions_core.gui.wizard_data import WizardData, storage_title

DURATION_KEEP_TEXT = "— разный у хранилищ (не менять) —"
LEVEL_COLORS = {"error": "#B71C1C", "warning": "#E65100", "info": "#1565C0"}
LEVEL_PREFIX = {"error": "✖ Ошибка", "warning": "⚠ Внимание", "info": "ℹ Подсказка"}


def _scroll(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(widget)
    return area


def _visible(form: ModelForm) -> dict[str, Any]:
    data = form.data()
    return {name: data[name] for name in form.visible_names()}


class ResultPanel(QLabel):
    """Панель промежуточного результата справа на шаге."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.setStyleSheet("background: #f5f7fa; border: 1px solid #d0d7de; border-radius: 4px; padding: 8px;")
        self.setMinimumWidth(280)

    def set_lines(self, title: str, lines: list[str]) -> None:
        self.setText(f"<b>{title}</b><br>" + "<br>".join(_html_line(line) for line in lines))

    def plain_text(self) -> str:
        return self.text()


def _html_line(line: str) -> str:
    text = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    if text.startswith("✖"):
        return f"<span style='color:#B71C1C'>{text}</span>"
    if text.startswith("⚠"):
        return f"<span style='color:#E65100'>{text}</span>"
    if text.startswith("✔"):
        return f"<span style='color:#1B5E20'>{text}</span>"
    return text.replace("    ", "&nbsp;&nbsp;&nbsp;&nbsp;")


class StepContent(QWidget):
    """Базовое содержимое шага: загрузка из общих данных и сигнал об изменении."""

    changed = Signal()

    def __init__(self, data: WizardData, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data = data
        self._loading = 0

    def load(self) -> None:
        self._loading += 1
        try:
            self._load()
        finally:
            self._loading -= 1

    def _load(self) -> None:
        raise NotImplementedError

    def _emit_changed(self) -> None:
        if not self._loading:
            self.changed.emit()

    def show_preview(self, result: ProjectCalculationResult | None) -> None:
        """Промежуточный результат (для шагов 2–5); по умолчанию не нужен."""


# ---------- шаг 1: проект ----------


class ProjectStep(StepContent):
    """Название склада, тип склада для всех хранилищ и методы расчета в «Дополнительно»."""

    def __init__(self, data: WizardData, parent: QWidget | None = None) -> None:
        super().__init__(data, parent)
        self._form = ModelForm(WarehouseProjectInput, self, fields=PROJECT_LAYOUT.basic, advanced=PROJECT_LAYOUT.advanced)
        self._duration = QComboBox(self)
        self._duration.addItem(DURATION_KEEP_TEXT, None)
        for value, label in enum_choices(WarehouseDuration):
            self._duration.addItem(label, value)
        self._duration.setToolTip(
            "Постоянный, временный или кратковременный склад. Применяется ко всем хранилищам "
            "и определяет требования к ограде, зонам и молниезащите."
        )
        type_row = QFormLayout()
        type_row.addRow(QLabel("Тип склада (для всех хранилищ)", self), self._duration)
        self._settings = ModelForm(CalculationSettings, self, fields=SETTINGS_LAYOUT.all_fields(), advanced=())
        self._settings_section = CollapsibleSection("Дополнительно: методы расчета", self._settings, self)
        hint = QLabel(
            "Значения методов расчета по умолчанию соответствуют Приказу № 343 (ред. 02.10.2025). "
            "Меняйте их, только если это требуется проектом.",
            self,
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #5f6b7a;")
        layout = QVBoxLayout(self)
        layout.addWidget(self._form)
        layout.addLayout(type_row)
        layout.addWidget(self._settings_section)
        layout.addWidget(hint)
        layout.addStretch(1)
        self._form.connect_changed(self._on_project_changed)
        self._settings.connect_changed(self._on_settings_changed)
        self._duration.currentIndexChanged.connect(self._on_duration_changed)

    def _load(self) -> None:
        self._form.set_data(self._data.project)
        self._settings.set_data(self._data.settings)
        common = self._data.common_duration()
        index = self._duration.findData(common) if common is not None else 0
        self._duration.setCurrentIndex(max(index, 0))

    def _on_project_changed(self) -> None:
        if self._loading:
            return
        self._data.project.update(_visible(self._form))
        self._emit_changed()

    def _on_settings_changed(self) -> None:
        if self._loading:
            return
        self._data.settings = self._settings.data()
        self._emit_changed()

    def _on_duration_changed(self, *_args) -> None:
        if self._loading:
            return
        value = self._duration.currentData()
        if value is not None:
            self._data.set_duration_for_all(value)
            self._emit_changed()

    def set_duration(self, duration: WarehouseDuration) -> None:
        self._duration.setCurrentIndex(self._duration.findData(duration.value))

    @property
    def settings_section(self) -> CollapsibleSection:
        return self._settings_section

    @property
    def form(self) -> ModelForm:
        return self._form


# ---------- шаги 2–5: хранилища ----------


class StorageListPanel(QWidget):
    """Список хранилищ слева. На шаге 2 — с кнопками «Добавить», «Копировать», «Удалить»."""

    selected = Signal(int)
    add_clicked = Signal()
    copy_clicked = Signal()
    remove_clicked = Signal()

    def __init__(self, with_buttons: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._list = QListWidget(self)
        self._list.currentRowChanged.connect(self._on_row)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("<b>Хранилища</b>", self))
        layout.addWidget(self._list, 1)
        if with_buttons:
            buttons = QHBoxLayout()
            for text, signal in (
                ("Добавить", self.add_clicked),
                ("Копировать", self.copy_clicked),
                ("Удалить", self.remove_clicked),
            ):
                button = QPushButton(text, self)
                button.clicked.connect(signal)
                buttons.addWidget(button)
            layout.addLayout(buttons)
        self.setMaximumWidth(260)

    def set_titles(self, titles: list[str], current: int) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for title in titles:
            self._list.addItem(QListWidgetItem(title))
        if titles:
            self._list.setCurrentRow(max(0, min(current, len(titles) - 1)))
        self._list.blockSignals(False)

    def set_title(self, index: int, title: str) -> None:
        item = self._list.item(index)
        if item is not None:
            item.setText(title)

    def current(self) -> int:
        return self._list.currentRow()

    def select(self, index: int) -> None:
        self._list.setCurrentRow(index)

    def count(self) -> int:
        return self._list.count()

    def _on_row(self, row: int) -> None:
        if row >= 0:
            self.selected.emit(row)


class StorageStep(StepContent):
    """Шаги 2–5: список хранилищ слева, поля шага выбранного хранилища и панель результата справа."""

    preview_title = "Результат"

    def __init__(self, data: WizardData, with_buttons: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(data, parent)
        self._list = StorageListPanel(with_buttons, self)
        self._storage_forms: list[ModelForm] = []
        self._design_forms: list[ModelForm] = []
        self._result: ProjectCalculationResult | None = None
        self._editor = QWidget(self)
        self._editor_layout = QVBoxLayout(self._editor)
        self._empty = QLabel("Нет хранилищ. Добавьте их на шаге «2. Хранилища и ВМ».", self)
        self._empty.setWordWrap(True)
        self._panel = ResultPanel(self)
        self._right = QWidget(self)
        right_layout = QVBoxLayout(self._right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self._build_right(right_layout)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._list)
        middle = QWidget(self)
        middle_layout = QVBoxLayout(middle)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.addWidget(self._empty)
        middle_layout.addWidget(_scroll(self._editor), 1)
        splitter.addWidget(middle)
        splitter.addWidget(self._right)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
        self._list.selected.connect(self._on_selected)
        self._list.add_clicked.connect(self.add_storage)
        self._list.copy_clicked.connect(self.copy_storage)
        self._list.remove_clicked.connect(self.remove_storage)

    def _build_right(self, layout: QVBoxLayout) -> None:
        layout.addWidget(self._panel, 1)

    def add_storage_form(self, fields, advanced=()) -> ModelForm:
        form = ModelForm(StorageBuilding, self._editor, fields=fields, advanced=advanced)
        form.connect_changed(self._on_storage_changed)
        self._storage_forms.append(form)
        self._editor_layout.addWidget(form)
        return form

    def add_design_form(self, fields, advanced=()) -> ModelForm:
        form = ModelForm(StorageDesignInput, self._editor, fields=fields, advanced=advanced)
        form.connect_changed(self._on_design_changed)
        self._design_forms.append(form)
        self._editor_layout.addWidget(form)
        return form

    def finish_editor(self) -> None:
        self._editor_layout.addStretch(1)

    # загрузка и выбор

    def _load(self) -> None:
        titles = [storage_title(s) for s in self._data.storages]
        self._list.set_titles(titles, self._data.selected_storage)
        self._load_selected()

    def _current(self) -> int:
        index = self._data.selected_storage
        return index if 0 <= index < self._data.storage_count() else -1

    def _load_selected(self) -> None:
        index = self._current()
        has = index >= 0
        self._editor.setEnabled(has)
        self._empty.setVisible(not has)
        self._loading += 1
        try:
            for form in self._storage_forms:
                form.set_data(self._data.storage(index) if has else None)
            for form in self._design_forms:
                form.set_data(self._data.design(index) if has else None)
        finally:
            self._loading -= 1
        self._refresh_panel()

    def _on_selected(self, row: int) -> None:
        if self._loading or row == self._data.selected_storage:
            return
        self._data.selected_storage = row
        self._load_selected()

    def select_storage(self, index: int) -> None:
        self._list.select(index)

    def selected_index(self) -> int:
        return self._current()

    # запись изменений

    def _on_storage_changed(self) -> None:
        index = self._current()
        if self._loading or index < 0:
            return
        for form in self._storage_forms:
            self._data.update_storage(index, _visible(form))
        self._list.set_title(index, storage_title(self._data.storage(index)))
        self._refresh_panel()
        self._emit_changed()

    def _on_design_changed(self) -> None:
        index = self._current()
        if self._loading or index < 0:
            return
        for form in self._design_forms:
            self._data.update_design(index, _visible(form))
        self._refresh_panel()
        self._emit_changed()

    # список хранилищ (кнопки шага 2)

    def add_storage(self) -> None:
        self._data.add_storage()
        self.load()
        self._emit_changed()

    def copy_storage(self) -> None:
        if self._current() < 0:
            return
        self._data.copy_storage(self._current())
        self.load()
        self._emit_changed()

    def remove_storage(self) -> None:
        if self._current() < 0:
            return
        self._data.remove_storage(self._current())
        self.load()
        self._emit_changed()

    # промежуточный результат

    def show_preview(self, result: ProjectCalculationResult | None) -> None:
        self._result = result
        self._refresh_panel()

    def _refresh_panel(self) -> None:
        index = self._current()
        if index < 0:
            self._panel.set_lines(self.preview_title, ["Выберите хранилище слева."])
            return
        self._panel.set_lines(self.preview_title, self.preview_lines(index))

    def preview_lines(self, index: int) -> list[str]:
        return []

    def panel_text(self) -> str:
        return self._panel.plain_text()

    def storage_forms(self) -> list[ModelForm]:
        return list(self._storage_forms)

    def design_forms(self) -> list[ModelForm]:
        return list(self._design_forms)


class StoragesStep(StorageStep):
    """Шаг 2: хранилища, их расположение и перечень ВМ; справа — проверка совместимости и шифров."""

    preview_title = "Проверка совместимости и шифров"

    def __init__(self, data: WizardData, parent: QWidget | None = None) -> None:
        super().__init__(data, with_buttons=True, parent=parent)
        self.general_form = self.add_storage_form(STORAGE_GENERAL_LAYOUT.basic, STORAGE_GENERAL_LAYOUT.advanced)
        self.finish_editor()

    def preview_lines(self, index: int) -> list[str]:
        return storage_check_lines(self._data.storage(index))


class SizingStep(StorageStep):
    """Шаг 3: тара и способ хранения; справа — число мест, высота груза и размеры здания."""

    preview_title = "Габариты по п. 579–580"

    def __init__(self, data: WizardData, parent: QWidget | None = None) -> None:
        super().__init__(data, parent=parent)
        self.sizing_form = self.add_design_form(SIZING_STEP_LAYOUT.basic, SIZING_STEP_LAYOUT.advanced)
        self.finish_editor()

    def preview_lines(self, index: int) -> list[str]:
        return sizing_preview_lines(self._result, self._data.key(index), self._data.design(index))


class PlacementStep(StorageStep):
    """Шаг 4: координаты и обвалование; справа — генплан с кругами r_д и параметры вала."""

    preview_title = "Размещение и обвалование"

    plan: PlanView

    def __init__(self, data: WizardData, parent: QWidget | None = None) -> None:
        super().__init__(data, parent=parent)
        self.building_form = self.add_storage_form(BUILDING_PLACEMENT_LAYOUT.basic, BUILDING_PLACEMENT_LAYOUT.advanced)
        self.berm_form = self.add_design_form(PLACEMENT_LAYOUT.basic, PLACEMENT_LAYOUT.advanced)
        self.finish_editor()

    def _build_right(self, layout: QVBoxLayout) -> None:
        self.plan = PlanView(self)
        layout.addWidget(self.plan, 3)
        layout.addWidget(self._panel, 2)

    def show_preview(self, result: ProjectCalculationResult | None) -> None:
        super().show_preview(result)
        if result is not None:
            self.plan.set_data(result.project, result)
            return
        try:
            project = WarehouseProjectInput.model_validate(self._data.to_dict()["project"])
        except ValueError:
            return
        self.plan.set_data(project, None)

    def preview_lines(self, index: int) -> list[str]:
        return placement_preview_lines(self._result, self._data.key(index), self._data.design(index))


class LightningStep(StorageStep):
    """Шаг 5: карниз, конек и мачты; справа — защищенность точек кровли и рекомендуемая высота мачт."""

    preview_title = "Молниезащита"

    def __init__(self, data: WizardData, parent: QWidget | None = None) -> None:
        super().__init__(data, parent=parent)
        self.lightning_form = self.add_design_form(LIGHTNING_STEP_LAYOUT.basic, LIGHTNING_STEP_LAYOUT.advanced)
        self.finish_editor()

    def preview_lines(self, index: int) -> list[str]:
        return lightning_preview_lines(self._result, self._data.key(index), self._data.design(index))


# ---------- шаги 6–7 ----------


class TerritoryStep(StepContent):
    """Шаг 6: ограда, запретная зона, зона запрета огня, ПРП и передвижной склад."""

    def __init__(self, data: WizardData, parent: QWidget | None = None) -> None:
        super().__init__(data, parent)
        self.form = ModelForm(WarehouseProjectInput, self, fields=TERRITORY_LAYOUT.basic, advanced=TERRITORY_LAYOUT.advanced)
        self.form.connect_changed(self._on_changed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(_scroll(self.form))

    def _load(self) -> None:
        self.form.set_data(self._data.project)

    def _on_changed(self) -> None:
        if self._loading:
            return
        self._data.project.update(_visible(self.form))
        self._emit_changed()


class TargetsStep(StepContent):
    """Шаг 7: внешние охраняемые объекты."""

    def __init__(self, data: WizardData, parent: QWidget | None = None) -> None:
        super().__init__(data, parent)
        self.table = ModelTable(ExternalProtectedObject, "Внешние объекты", self)
        self.table.connect_changed(self._on_changed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(_scroll(self.table))

    def _load(self) -> None:
        self.table.set_data(self._data.targets)

    def _on_changed(self) -> None:
        if self._loading:
            return
        self._data.targets = self.table.data()
        self._emit_changed()


# ---------- шаг 8 ----------


class CalculationStep(StepContent):
    """Шаг 8: список недостающих данных, расчет, результаты, генплан и выгрузка."""

    calculate_requested = Signal()
    export_requested = Signal()
    step_requested = Signal(int)

    def __init__(self, data: WizardData, parent: QWidget | None = None) -> None:
        super().__init__(data, parent)
        self._items: list[ReadinessItem] = []
        self._summary = QLabel(self)
        self._summary.setWordWrap(True)
        self._list = QListWidget(self)
        self._list.setWordWrap(True)
        self._list.setMaximumHeight(170)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        self._calculate = QPushButton("Рассчитать (F5)", self)
        self._export = QPushButton("Выгрузить DXF, DOCX, JSON…", self)
        self._calculate.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        self._calculate.clicked.connect(self.calculate_requested)
        self._export.clicked.connect(self.export_requested)
        buttons = QHBoxLayout()
        buttons.addWidget(self._calculate)
        buttons.addWidget(self._export)
        buttons.addStretch(1)
        self.results_page = ResultsPage(self)
        self.plan_page = PlanPage(self)
        self._tabs = QTabWidget(self)
        self._tabs.addTab(self.results_page, "Результаты")
        self._tabs.addTab(self.plan_page, "Генплан")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("<b>Проверка данных</b> (двойной щелчок по строке — переход к шагу)", self))
        layout.addWidget(self._summary)
        layout.addWidget(self._list)
        layout.addLayout(buttons)
        layout.addWidget(self._tabs, 1)

    def _load(self) -> None:
        """Данные шага приходят из окна: список проверки и результат."""

    def set_readiness(self, items: list[ReadinessItem], schema_error: str | None = None) -> None:
        self._items = list(items)
        self._list.clear()
        if schema_error:
            self._summary.setText(f"<span style='color:#B71C1C'>Данные не проходят проверку схемы:</span> {schema_error}")
            return
        errors = sum(1 for item in items if item.level == "error")
        warnings = sum(1 for item in items if item.level == "warning")
        if not items:
            self._summary.setText("<span style='color:#1B5E20'>✔ Все данные для расчета заполнены.</span>")
        elif errors:
            self._summary.setText(
                f"<span style='color:#B71C1C'>Ошибок: {errors}</span>, предупреждений: {warnings}. "
                "Исправьте ошибки, иначе расчет не выполнится."
            )
        else:
            self._summary.setText(f"Предупреждений: {warnings}. Расчет можно выполнить.")
        for item in items:
            where = f" [{item.storage}]" if item.storage else ""
            entry = QListWidgetItem(f"{LEVEL_PREFIX[item.level]}{where}: {item.message} — {item.hint}")
            entry.setForeground(QBrush(QColor(LEVEL_COLORS[item.level])))
            entry.setToolTip(item.hint)
            self._list.addItem(entry)

    def readiness_count(self) -> int:
        return self._list.count()

    def _on_double_click(self, *_args) -> None:
        row = self._list.currentRow()
        if 0 <= row < len(self._items):
            self.step_requested.emit(self._items[row].step)

    def activate_row(self, row: int) -> None:
        """Тот же переход, что и по двойному щелчку (для клавиатуры и тестов)."""
        self._list.setCurrentRow(row)
        self._on_double_click()

    def show_results_tab(self) -> None:
        self._tabs.setCurrentWidget(self.results_page)
