"""Формы редактирования моделей pydantic: поля строятся по схеме модели, данные собираются обратно в dict.

Одна схема (`ProjectDefinition.model_validate`) проверяет и формы, и файл проекта, поэтому правила
не дублируются в интерфейсе. Вложенные модели — вложенные формы, списки моделей — таблицы строк.
Во время заполнения формы из данных сигналы об изменении подавляются (`_loading`), иначе частично
заполненная форма записалась бы обратно в данные.
"""

import types
from enum import Enum
from typing import Any, Callable, Union, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from explosions_core.gui.help_texts import field_help
from explosions_core.gui.labels import field_label
from explosions_core.gui.layouts import layout_for_model
from explosions_core.gui.widgets import (
    BoolEditor,
    CollapsibleSection,
    EnumEditor,
    FloatEditor,
    IntEditor,
    OptionalEditor,
    TextEditor,
    float_range,
    int_range,
)

_NONE_TYPE = type(None)
ADVANCED_TITLE = "Дополнительно"
ROW_TITLE_KEYS = ("name", "object_id", "mast_id", "vehicle_name", "storage_id")


def _unwrap_optional(annotation: Any) -> tuple[Any, bool]:
    """Возвращает (базовый тип, допускает ли None) для аннотаций `T | None` и `Optional[T]`."""
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        args = [arg for arg in get_args(annotation) if arg is not _NONE_TYPE]
        optional = len(args) < len(get_args(annotation))
        if len(args) == 1:
            return args[0], optional
        return annotation, optional
    return annotation, False


def _bounds(info: FieldInfo) -> dict[str, float]:
    bounds: dict[str, float] = {}
    for meta in info.metadata:
        for key in ("ge", "gt", "le", "lt"):
            value = getattr(meta, key, None)
            if value is not None:
                bounds[key] = float(value)
    return bounds


def _default_of(info: FieldInfo) -> Any:
    """Значение по умолчанию для пустой формы; обязательные поля — None (пустой редактор)."""
    if info.default is PydanticUndefined or info.default_factory is not None:
        return None
    return info.default


def _resolve_layout(
    model_cls: type[BaseModel],
    fields: list[str] | tuple[str, ...] | None,
    advanced: list[str] | tuple[str, ...] | None,
) -> tuple[list[str], list[str]]:
    """Поля на виду и поля «Дополнительно»: явные списки, иначе раскладка модели, иначе все поля."""
    if fields is None and advanced is None:
        layout = layout_for_model(model_cls)
        if layout is None:
            return list(model_cls.model_fields), []
        return list(layout.basic), list(layout.advanced)
    return list(fields or []), list(advanced or [])


def is_model_type(annotation: Any) -> bool:
    return isinstance(annotation, type) and issubclass(annotation, BaseModel)


def is_list_of_models(annotation: Any) -> tuple[bool, type | None]:
    origin = get_origin(annotation)
    if origin is list:
        args = get_args(annotation)
        if args and is_model_type(args[0]):
            return True, args[0]
    return False, None


def create_scalar_editor(annotation: Any, info: FieldInfo, parent: QWidget | None = None) -> QWidget:
    """Редактор для скалярного поля по аннотации и ограничениям модели."""
    base, optional = _unwrap_optional(annotation)
    bounds = _bounds(info)
    if isinstance(base, type) and issubclass(base, Enum):
        return EnumEditor(base, optional=optional, parent=parent)
    if base is bool:
        return BoolEditor(parent)
    if base is int:
        minimum, maximum = int_range(bounds)
        inner: QWidget = IntEditor(minimum, maximum, parent)
    elif base is float:
        minimum, maximum = float_range(bounds)
        inner = FloatEditor(minimum, maximum, parent)
    else:
        return TextEditor(optional=optional, parent=parent)
    if optional:
        return OptionalEditor(inner, parent)
    return inner


class _Loadable:
    """Общее подавление сигналов на время загрузки данных."""

    def __init__(self) -> None:
        self._loading = 0
        self._listeners: list[Callable[[], None]] = []

    def connect_changed(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def _notify(self) -> None:
        if self._loading:
            return
        for callback in list(self._listeners):
            callback()


class ModelForm(_Loadable, QWidget):
    """Форма одной модели: строка QFormLayout на скалярное поле, группа на вложенную модель, таблица на список.

    `fields` — поля на виду, `advanced` — поля свернутого блока «Дополнительно». Если оба не заданы,
    берется раскладка модели из `layouts.MODEL_LAYOUTS`, а без нее показываются все поля.
    Остальные поля скрыты, но их значения сохраняются в `data()`: поля вне раскладки шага не теряются
    и не превращаются в значения по умолчанию.
    """

    def __init__(
        self,
        model_cls: type[BaseModel],
        parent: QWidget | None = None,
        fields: list[str] | tuple[str, ...] | None = None,
        advanced: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        _Loadable.__init__(self)
        QWidget.__init__(self, parent)
        self.model_cls = model_cls
        self._editors: dict[str, QWidget] = {}
        self._children: dict[str, Any] = {}
        self._defaults: dict[str, Any] = {}
        self._hidden: dict[str, Any] = {}
        self._labels: dict[str, QWidget] = {}
        self._layout = QFormLayout(self)
        self._layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        basic, extra = _resolve_layout(model_cls, fields, advanced)
        self._shown = set(basic) | set(extra)
        self._hidden_names = [name for name in model_cls.model_fields if name not in self._shown]
        for name in basic:
            self._add_field(name, model_cls.model_fields[name], self._layout)
        self.advanced_section: CollapsibleSection | None = None
        if extra:
            container = QWidget(self)
            advanced_layout = QFormLayout(container)
            advanced_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            for name in extra:
                self._add_field(name, model_cls.model_fields[name], advanced_layout)
            self.advanced_section = CollapsibleSection(ADVANCED_TITLE, container, self)
            self._layout.addRow(self.advanced_section)
        for name in self._hidden_names:
            self._defaults[name] = _default_of(model_cls.model_fields[name])

    def _add_field(self, name: str, info: FieldInfo, target: QFormLayout) -> None:
        annotation = info.annotation
        label = field_label(name)
        base, optional = _unwrap_optional(annotation)
        is_list, row_model = is_list_of_models(base)
        self._defaults[name] = _default_of(info)
        help_text = field_help(self.model_cls.__name__, name)
        if is_model_type(base):
            group: QWidget = (
                OptionalModelGroup(label, base, self) if optional else NestedModelGroup(label, base, self)
            )
            self._children[name] = group
            group.connect_changed(self._notify)
            if help_text:
                group.setToolTip(help_text)
            target.addRow(group)
        elif is_list and row_model is not None:
            table = ModelTable(row_model, label, self)
            self._children[name] = table
            table.connect_changed(self._notify)
            if help_text:
                table.setToolTip(help_text)
            target.addRow(table)
        else:
            editor = create_scalar_editor(annotation, info, self)
            self._editors[name] = editor
            label_widget = QLabel(label, self)
            self._labels[name] = label_widget
            if help_text:
                label_widget.setToolTip(help_text)
                editor.setToolTip(help_text)
            target.addRow(label_widget, editor)
            editor.connect_changed(self._notify)

    def set_data(self, data: dict[str, Any] | None) -> None:
        values = data or {}
        self._loading += 1
        try:
            self._hidden = {name: values[name] for name in self._hidden_names if name in values}
            for name, editor in self._editors.items():
                editor.put_value(values[name] if name in values else self._defaults[name])
            for name, child in self._children.items():
                child.set_data(values[name] if name in values else None)
        finally:
            self._loading -= 1

    def data(self) -> dict[str, Any]:
        result: dict[str, Any] = dict(self._hidden)
        result.update({name: editor.get_value() for name, editor in self._editors.items()})
        for name, child in self._children.items():
            result[name] = child.data()
        return result

    def visible_names(self) -> list[str]:
        return [name for name in self.model_cls.model_fields if name in self._shown]

    def has_field(self, name: str) -> bool:
        return name in self._editors or name in self._children

    def editor(self, name: str) -> QWidget:
        return self._editors[name]

    def tooltip_of(self, name: str) -> str:
        if name in self._labels:
            return self._labels[name].toolTip()
        if name in self._children:
            return self._children[name].toolTip()
        return ""

    def child(self, name: str) -> Any:
        return self._children[name]


class NestedModelGroup(QGroupBox):
    """Обязательная вложенная модель: всегда заполнена."""

    def __init__(self, title: str, model_cls: type[BaseModel], parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self._form = ModelForm(model_cls, self)
        self._form.connect_changed(self._notify)
        layout = QVBoxLayout(self)
        layout.addWidget(self._form)
        self._listeners: list[Callable[[], None]] = []

    def connect_changed(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def _notify(self) -> None:
        for callback in list(self._listeners):
            callback()

    def set_data(self, data: dict[str, Any] | None) -> None:
        self._form.set_data(data)

    def data(self) -> dict[str, Any]:
        return self._form.data()

    @property
    def form(self) -> ModelForm:
        return self._form


class OptionalModelGroup(QGroupBox):
    """Необязательная вложенная модель: снятый флажок в заголовке даёт `None`."""

    def __init__(self, title: str, model_cls: type[BaseModel], parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(False)
        self._form = ModelForm(model_cls, self)
        self._form.setEnabled(False)
        self._listeners: list[Callable[[], None]] = []
        layout = QVBoxLayout(self)
        layout.addWidget(self._form)
        self.toggled.connect(self._form.setEnabled)
        self.toggled.connect(lambda *_: self._notify())
        self._form.connect_changed(self._notify)

    def connect_changed(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def _notify(self) -> None:
        for callback in list(self._listeners):
            callback()

    def set_data(self, data: dict[str, Any] | None) -> None:
        self.blockSignals(True)
        self.setChecked(data is not None)
        self.blockSignals(False)
        self._form.setEnabled(data is not None)
        self._form.set_data(data)

    def data(self) -> dict[str, Any] | None:
        if not self.isChecked():
            return None
        return self._form.data()

    @property
    def form(self) -> ModelForm:
        return self._form


class ModelTable(_Loadable, QWidget):
    """Список моделей-строк. Редактирование — через форму выбранной строки, слева — список строк."""

    def __init__(self, row_model: type[BaseModel], title: str, parent: QWidget | None = None) -> None:
        _Loadable.__init__(self)
        QWidget.__init__(self, parent)
        self.row_model = row_model
        self._rows: list[dict[str, Any]] = []
        self._current = -1
        self._table = QTableWidget(0, 1, self)
        self._table.setHorizontalHeaderLabels([title])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setMaximumHeight(120)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._form = ModelForm(row_model, self)
        self._form.connect_changed(self._on_form_changed)
        self._add_button = QPushButton("Добавить", self)
        self._copy_button = QPushButton("Копировать", self)
        self._remove_button = QPushButton("Удалить", self)
        self._add_button.clicked.connect(self.add_row)
        self._copy_button.clicked.connect(self.copy_row)
        self._remove_button.clicked.connect(self.remove_row)
        buttons = QHBoxLayout()
        for button in (self._add_button, self._copy_button, self._remove_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._table)
        layout.addLayout(buttons)
        layout.addWidget(self._form)
        self._show_empty()

    def set_data(self, data: list[dict[str, Any]] | None) -> None:
        self._loading += 1
        try:
            self._rows = [dict(row) for row in (data or [])]
            self._current = -1
            self._rebuild_table()
            if self._rows:
                self._select(0)
            else:
                self._show_empty()
        finally:
            self._loading -= 1

    def data(self) -> list[dict[str, Any]]:
        self._commit_current()
        return [dict(row) for row in self._rows]

    def row_count(self) -> int:
        return len(self._rows)

    def select_row(self, index: int) -> None:
        self._commit_current()
        self._select(index)

    def add_row(self) -> None:
        self._commit_current()
        self._rows.append({})
        self._rebuild_table()
        self._select(len(self._rows) - 1)
        self._notify()

    def copy_row(self) -> None:
        if not self._has_selection():
            return
        self._commit_current()
        self._rows.append(dict(self._rows[self._current]))
        self._rebuild_table()
        self._select(len(self._rows) - 1)
        self._notify()

    def remove_row(self) -> None:
        if not self._has_selection():
            return
        removed = self._current
        self._rows.pop(removed)
        self._current = -1
        self._rebuild_table()
        if self._rows:
            self._select(min(removed, len(self._rows) - 1))
        else:
            self._show_empty()
        self._notify()

    def _has_selection(self) -> bool:
        return 0 <= self._current < len(self._rows)

    def _show_empty(self) -> None:
        self._current = -1
        self._loading += 1
        try:
            self._form.set_data(None)
        finally:
            self._loading -= 1
        self._form.setEnabled(False)
        self._refresh_buttons()

    def _commit_current(self) -> None:
        if self._has_selection():
            self._rows[self._current] = self._form.data()

    def _rebuild_table(self) -> None:
        self._table.blockSignals(True)
        self._table.setRowCount(len(self._rows))
        for index, row in enumerate(self._rows):
            self._table.setItem(index, 0, QTableWidgetItem(self._row_title(row, index)))
        self._table.blockSignals(False)

    @staticmethod
    def _row_title(row: dict[str, Any], index: int) -> str:
        for key in ROW_TITLE_KEYS:
            value = row.get(key)
            if value:
                return str(value)
        return f"Строка {index + 1}"

    def _select(self, index: int) -> None:
        if not (0 <= index < len(self._rows)):
            return
        self._current = index
        self._table.blockSignals(True)
        self._table.selectRow(index)
        self._table.blockSignals(False)
        self._form.setEnabled(True)
        self._loading += 1
        try:
            self._form.set_data(self._rows[index])
        finally:
            self._loading -= 1
        self._refresh_buttons()

    def _on_selection_changed(self) -> None:
        index = self._table.currentRow()
        if index < 0 or index == self._current:
            return
        self._commit_current()
        self._select(index)

    def _on_form_changed(self) -> None:
        if self._loading or not self._has_selection():
            return
        self._rows[self._current] = self._form.data()
        item = self._table.item(self._current, 0)
        if item is not None:
            self._table.blockSignals(True)
            item.setText(self._row_title(self._rows[self._current], self._current))
            self._table.blockSignals(False)
        self._notify()

    def _refresh_buttons(self) -> None:
        has_selection = self._has_selection()
        self._copy_button.setEnabled(has_selection)
        self._remove_button.setEnabled(has_selection)

    @property
    def form(self) -> ModelForm:
        return self._form
