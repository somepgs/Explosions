"""Редакторы скалярных значений для форм интерфейса (PySide6).

Каждый редактор реализует единый интерфейс: `get_value()`, `put_value(value)` и `connect_changed(callback)`.
Значение `None` в необязательном поле отображается как снятый флажок «задано» или пустой выбор.
"""

from enum import Enum
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from explosions_core.gui.labels import enum_choices

NO_VALUE_TEXT = "— не задано —"
FLOAT_LIMIT = 1.0e12
INT_LIMIT = 1_000_000_000
FLOAT_DECIMALS = 4


class FloatEditor(QDoubleSpinBox):
    """Число с 4 знаками на экране. Точное загруженное значение сохраняется, пока пользователь его не изменит:
    иначе простой просмотр формы округлял бы данные проекта."""

    def __init__(self, minimum: float = -FLOAT_LIMIT, maximum: float = FLOAT_LIMIT, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDecimals(FLOAT_DECIMALS)
        self.setRange(minimum, maximum)
        self.setSingleStep(0.1)
        self._exact: float | None = None

    def get_value(self) -> float:
        shown = float(self.value())
        if self._exact is not None and round(self._exact, FLOAT_DECIMALS) == shown:
            return self._exact
        return shown

    def put_value(self, value: Any) -> None:
        self._exact = None if value is None else float(value)
        self.setValue(0.0 if value is None else float(value))

    def connect_changed(self, callback: Callable[[], None]) -> None:
        self.valueChanged.connect(lambda *_: callback())


class IntEditor(QSpinBox):
    def __init__(self, minimum: int = 0, maximum: int = INT_LIMIT, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setRange(minimum, maximum)

    def get_value(self) -> int:
        return int(self.value())

    def put_value(self, value: Any) -> None:
        self.setValue(0 if value is None else int(value))

    def connect_changed(self, callback: Callable[[], None]) -> None:
        self.valueChanged.connect(lambda *_: callback())


class BoolEditor(QCheckBox):
    def get_value(self) -> bool:
        return self.isChecked()

    def put_value(self, value: Any) -> None:
        self.setChecked(bool(value))

    def connect_changed(self, callback: Callable[[], None]) -> None:
        self.toggled.connect(lambda *_: callback())


class TextEditor(QLineEdit):
    def __init__(self, optional: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._optional = optional

    def get_value(self) -> str | None:
        text = self.text().strip()
        if self._optional and not text:
            return None
        return text

    def put_value(self, value: Any) -> None:
        self.setText("" if value is None else str(value))

    def connect_changed(self, callback: Callable[[], None]) -> None:
        self.textChanged.connect(lambda *_: callback())


class EnumEditor(QComboBox):
    def __init__(self, enum_type: type[Enum], optional: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._optional = optional
        if optional:
            self.addItem(NO_VALUE_TEXT, None)
        for value, label in enum_choices(enum_type):
            self.addItem(label, value)

    def get_value(self) -> str | None:
        return self.currentData()

    def put_value(self, value: Any) -> None:
        raw = getattr(value, "value", value)
        index = self.findData(raw) if raw is not None else -1
        if index < 0:
            index = 0
        self.setCurrentIndex(index)

    def connect_changed(self, callback: Callable[[], None]) -> None:
        self.currentIndexChanged.connect(lambda *_: callback())


class OptionalEditor(QWidget):
    """Необязательное число: флажок «задано» + редактор. Снятый флажок даёт `None`."""

    def __init__(self, inner: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._inner = inner
        self._flag = QCheckBox("задано", self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._flag)
        layout.addWidget(inner, 1)
        self._flag.toggled.connect(self._sync_enabled)
        self._sync_enabled(False)

    def _sync_enabled(self, checked: bool) -> None:
        self._inner.setEnabled(checked)

    def get_value(self) -> Any:
        if not self._flag.isChecked():
            return None
        return self._inner.get_value()

    def put_value(self, value: Any) -> None:
        self._flag.setChecked(value is not None)
        self._inner.put_value(value)

    def connect_changed(self, callback: Callable[[], None]) -> None:
        self._flag.toggled.connect(lambda *_: callback())
        self._inner.connect_changed(callback)


class CollapsibleSection(QWidget):
    """Сворачиваемый блок «Дополнительно»: кнопка-заголовок и содержимое, скрытое по умолчанию."""

    def __init__(self, title: str, content: QWidget, parent: QWidget | None = None, expanded: bool = False) -> None:
        super().__init__(parent)
        self._toggle = QToolButton(self)
        self._toggle.setText(title)
        self._toggle.setCheckable(True)
        self._toggle.setChecked(expanded)
        self._toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self._toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle.setStyleSheet("QToolButton { border: none; font-weight: bold; }")
        self._content = content
        self._content.setVisible(expanded)
        self._toggle.toggled.connect(self._on_toggled)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._toggle)
        layout.addWidget(self._content)

    def _on_toggled(self, checked: bool) -> None:
        self._toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        self._content.setVisible(checked)

    def is_expanded(self) -> bool:
        return self._toggle.isChecked()

    def set_expanded(self, expanded: bool) -> None:
        self._toggle.setChecked(expanded)


def float_range(bounds: dict[str, float]) -> tuple[float, float]:
    """Диапазон спинбокса по ограничениям модели (`ge`, `gt`, `le`, `lt`)."""
    step = 10.0 ** -FLOAT_DECIMALS
    minimum = bounds["ge"] if "ge" in bounds else (bounds["gt"] + step if "gt" in bounds else -FLOAT_LIMIT)
    maximum = bounds["le"] if "le" in bounds else (bounds["lt"] - step if "lt" in bounds else FLOAT_LIMIT)
    return minimum, maximum


def int_range(bounds: dict[str, float]) -> tuple[int, int]:
    minimum = int(bounds["ge"]) if "ge" in bounds else (int(bounds["gt"]) + 1 if "gt" in bounds else 0)
    maximum = int(bounds["le"]) if "le" in bounds else (int(bounds["lt"]) - 1 if "lt" in bounds else INT_LIMIT)
    return minimum, maximum
