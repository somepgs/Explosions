"""Обёртка шага мастера: заголовок, инструкция сверху, содержимое, кнопки «Назад» и «Далее» снизу."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class StepPage(QWidget):
    """Шаг мастера. Содержимое вставляется через `set_content`: одна страница раздела может быть на нескольких шагах."""

    back_requested = Signal()
    next_requested = Signal()

    def __init__(self, title: str, instruction: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = QLabel(title, self)
        self._title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self._instruction = QLabel(instruction, self)
        self._instruction.setWordWrap(True)
        self._instruction.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._instruction.setStyleSheet("color: #33414e; background: #eef3f8; padding: 8px; border-radius: 4px;")
        self._back = QPushButton("← Назад", self)
        self._next = QPushButton("Далее →", self)
        self._back.clicked.connect(self.back_requested)
        self._next.clicked.connect(self.next_requested)
        buttons = QHBoxLayout()
        buttons.addWidget(self._back)
        buttons.addStretch(1)
        buttons.addWidget(self._next)
        self._body = QVBoxLayout()
        layout = QVBoxLayout(self)
        layout.addWidget(self._title)
        layout.addWidget(self._instruction)
        layout.addLayout(self._body, 1)
        layout.addLayout(buttons)
        self._content: QWidget | None = None

    def set_content(self, content: QWidget) -> None:
        """Ставит страницу раздела в шаг: прежнее содержимое убирается из этого шага, но не удаляется."""
        if self._content is content:
            return
        if self._content is not None:
            self._body.removeWidget(self._content)
            self._content.hide()
        content.show()
        self._body.addWidget(content, 1)
        self._content = content

    @property
    def content(self) -> QWidget | None:
        return self._content

    def set_back_enabled(self, enabled: bool) -> None:
        self._back.setEnabled(enabled)

    def set_next_enabled(self, enabled: bool) -> None:
        self._next.setEnabled(enabled)

    def title_text(self) -> str:
        return self._title.text()

    def instruction_text(self) -> str:
        return self._instruction.text()
