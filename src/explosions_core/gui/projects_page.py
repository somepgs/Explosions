"""Стартовый экран «Проекты»: список проектов из базы SQLite и основные действия (PySide6)."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from explosions_core.io.project_db import ProjectDatabase, ProjectDatabaseError, ProjectRecord

INTRO_TEXT = (
    "Здесь хранятся ваши проекты складов ВМ. Создайте новый проект, откройте сохраненный двойным щелчком "
    "или посмотрите пример. После открытия заполняйте шаги 1–8 в списке слева."
)


class ProjectsPage(QWidget):
    """Список проектов базы. Действия передаются окну сигналами: окно отвечает за несохраненные изменения."""

    new_requested = Signal()
    open_requested = Signal(int)
    copy_requested = Signal(int)
    delete_requested = Signal(int)
    import_requested = Signal()
    example_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._database: ProjectDatabase | None = None
        self._records: list[ProjectRecord] = []
        title = QLabel("Проекты", self)
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        intro = QLabel(INTRO_TEXT, self)
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #33414e; background: #eef3f8; padding: 8px; border-radius: 4px;")
        self._table = QTableWidget(0, 2, self)
        self._table.setHorizontalHeaderLabels(["Проект", "Изменен"])
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.itemDoubleClicked.connect(lambda *_: self._emit_for_selected(self.open_requested))
        self._table.itemSelectionChanged.connect(self._refresh_buttons)
        self._empty = QLabel("В базе пока нет проектов. Нажмите «Новый проект» или «Открыть пример».", self)
        self._empty.setWordWrap(True)
        self._new = QPushButton("Новый проект", self)
        self._open = QPushButton("Открыть", self)
        self._copy = QPushButton("Копировать", self)
        self._delete = QPushButton("Удалить", self)
        self._import = QPushButton("Импорт из JSON…", self)
        self._example = QPushButton("Открыть пример", self)
        self._new.setStyleSheet("font-weight: bold;")
        self._new.clicked.connect(self.new_requested)
        self._open.clicked.connect(lambda: self._emit_for_selected(self.open_requested))
        self._copy.clicked.connect(lambda: self._emit_for_selected(self.copy_requested))
        self._delete.clicked.connect(lambda: self._emit_for_selected(self.delete_requested))
        self._import.clicked.connect(self.import_requested)
        self._example.clicked.connect(self.example_requested)
        buttons = QHBoxLayout()
        for button in (self._new, self._open, self._copy, self._delete):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(self._import)
        buttons.addWidget(self._example)
        self._location = QLabel(self)
        self._location.setWordWrap(True)
        self._location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._location.setStyleSheet("color: #5f6b7a;")
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(intro)
        layout.addLayout(buttons)
        layout.addWidget(self._empty)
        layout.addWidget(self._table, 1)
        layout.addWidget(self._location)
        self.refresh()

    def set_database(self, database: ProjectDatabase | None) -> None:
        self._database = database
        self.refresh()

    def set_example_available(self, available: bool) -> None:
        self._example.setEnabled(available)

    def refresh(self) -> None:
        error = None
        if self._database is None:
            self._records = []
            self._location.setText("База данных не подключена: проекты можно открывать и сохранять только в файлах JSON.")
        else:
            try:
                self._records = self._database.list_projects()
            except ProjectDatabaseError as exc:
                self._records = []
                error = str(exc)
            self._location.setText(f"База данных проектов: {self._database.path}")
        self._table.setRowCount(len(self._records))
        for row, record in enumerate(self._records):
            self._table.setItem(row, 0, QTableWidgetItem(record.name))
            self._table.setItem(row, 1, QTableWidgetItem(record.updated_at))
        self._table.resizeColumnToContents(1)
        self._empty.setVisible(not self._records)
        if error:
            self._empty.setText(f"Не удалось прочитать базу данных: {error}")
        if self._records:
            self._table.selectRow(0)
        self._refresh_buttons()

    def record_count(self) -> int:
        return len(self._records)

    def record_names(self) -> list[str]:
        return [record.name for record in self._records]

    def select_row(self, row: int) -> None:
        self._table.selectRow(row)

    def selected_id(self) -> int | None:
        row = self._table.currentRow()
        if 0 <= row < len(self._records):
            return self._records[row].id
        return None

    def _emit_for_selected(self, signal) -> None:
        project_id = self.selected_id()
        if project_id is not None:
            signal.emit(project_id)

    def _refresh_buttons(self) -> None:
        has = self.selected_id() is not None
        for button in (self._open, self._copy, self._delete):
            button.setEnabled(has)
        self._new.setEnabled(True)

    def request_open(self) -> None:
        self._emit_for_selected(self.open_requested)

    def request_copy(self) -> None:
        self._emit_for_selected(self.copy_requested)

    def request_delete(self) -> None:
        self._emit_for_selected(self.delete_requested)
