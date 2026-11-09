"""Страницы результатов и генплана для шага «Проверка и расчет» (PySide6)."""

from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from explosions_core.domain import ProjectCalculationResult
from explosions_core.gui.explanations import explain_violation
from explosions_core.gui.plan_view import PlanView
from explosions_core.gui.results_view import (
    STATUS_FAIL,
    STATUS_OK,
    STATUS_WARN,
    berm_rows,
    detonation_rows,
    issue_rows,
    lightning_rows,
    overall_status,
    sizing_rows,
    uvv_rows,
    violation_rows,
)

BANNER_COLORS = {
    STATUS_OK: ("#1B5E20", "#E8F5E9"),
    STATUS_WARN: ("#E65100", "#FFF3E0"),
    STATUS_FAIL: ("#B71C1C", "#FFEBEE"),
}
VIOLATION_BRUSH = QBrush(QColor("#B71C1C"))
VIOLATION_HEADERS = ["Код", "Описание", "Факт", "Норма", "Пункт НПА", "Что сделать"]


def _fill_table(table: QTableWidget, headers: list[str], rows: list[list[str]], red_rows: set[int] | None = None) -> None:
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            item = QTableWidgetItem(text)
            item.setToolTip(text)
            if red_rows and r in red_rows:
                item.setForeground(VIOLATION_BRUSH)
            table.setItem(r, c, item)
    table.resizeColumnsToContents()
    table.horizontalHeader().setStretchLastSection(True)


def _make_table() -> QTableWidget:
    table = QTableWidget(0, 0)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setWordWrap(True)
    return table


class ResultsPage(QWidget):
    """Результаты расчета: баннер статуса и вкладки с таблицами. Нарушения подсвечиваются красным."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._banner = QLabel(self)
        self._banner.setWordWrap(True)
        self._banner.setStyleSheet("padding: 10px; border-radius: 6px; font-weight: bold;")
        self._tabs = QTabWidget(self)
        self._violations = _make_table()
        self._issues = _make_table()
        self._detonation = _make_table()
        self._uvv = _make_table()
        self._sizing = _make_table()
        self._berm = _make_table()
        self._lightning = _make_table()
        self._tabs.addTab(self._violations, "Нарушения")
        self._tabs.addTab(self._issues, "Замечания")
        self._tabs.addTab(self._detonation, "Передача детонации r_д")
        self._tabs.addTab(self._uvv, "Ударная волна R_увв")
        self._tabs.addTab(self._sizing, "Габариты")
        self._tabs.addTab(self._berm, "Обвалование")
        self._tabs.addTab(self._lightning, "Молниезащита")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._banner)
        layout.addWidget(self._tabs, 1)
        self.clear()

    def clear(self) -> None:
        self._banner.setText("Расчет не выполнен. Нажмите «Рассчитать» (F5).")
        self._set_banner_style(STATUS_WARN)
        for table in (self._violations, self._issues, self._detonation, self._uvv, self._sizing, self._berm, self._lightning):
            table.setRowCount(0)
            table.setColumnCount(0)

    def show_result(self, result: ProjectCalculationResult) -> None:
        status, text = overall_status(result)
        self._banner.setText(text)
        self._set_banner_style(status)
        violations = result.all_violations
        rows = [row + [explain_violation(v).action] for row, v in zip(violation_rows(violations), violations)]
        _fill_table(self._violations, VIOLATION_HEADERS, rows, red_rows=set(range(len(violations))))
        _fill_table(self._issues, ["Тип", "Модуль", "Объект", "Сообщение"], issue_rows(result.issues))
        _fill_table(
            self._detonation,
            ["Пара", "Q_i, кг", "Q_j, кг", "r_д, м", "L_факт, м", "Запас, м", "Статус"],
            detonation_rows(result),
            red_rows=_red(detonation_rows(result), "НАРУШЕНИЕ"),
        )
        _fill_table(
            self._uvv,
            ["Хранилище", "Объект", "Q, кг", "R_увв, м", "Факт, м", "Запас, м", "Статус"],
            uvv_rows(result),
            red_rows=_red(uvv_rows(result), "НАРУШЕНИЕ"),
        )
        _fill_table(
            self._sizing,
            ["Хранилище", "Мест", "Ярусов", "Высота груза, м", "W, м", "L, м", "H, м", "Статус"],
            sizing_rows(result),
            red_rows=_red(sizing_rows(result), "НАРУШЕНИЕ"),
        )
        _fill_table(
            self._berm,
            ["Хранилище", "H_в, м", "b_гр, м", "B_под, м", "V, м³", "Статус"],
            berm_rows(result),
            red_rows=_red(berm_rows(result), "НАРУШЕНИЕ"),
        )
        _fill_table(
            self._lightning,
            ["Хранилище", "Метод", "Высота мачты, м", "Покрыто", "Статус"],
            lightning_rows(result),
            red_rows=_red(lightning_rows(result), "НАРУШЕНИЕ"),
        )
        if not violations and result.issues:
            self._tabs.setCurrentWidget(self._issues)
        else:
            self._tabs.setCurrentWidget(self._violations)

    def _set_banner_style(self, status: str) -> None:
        color, background = BANNER_COLORS.get(status, BANNER_COLORS[STATUS_WARN])
        self._banner.setStyleSheet(
            f"padding: 10px; border-radius: 6px; font-weight: bold; color: {color}; background: {background};"
        )

    def tab_titles(self) -> list[str]:
        return [self._tabs.tabText(i) for i in range(self._tabs.count())]

    def table(self, title: str) -> QTableWidget:
        for index in range(self._tabs.count()):
            if self._tabs.tabText(index) == title:
                return self._tabs.widget(index)
        raise KeyError(title)

    def banner_text(self) -> str:
        return self._banner.text()


def _red(rows: list[list[str]], marker: str) -> set[int]:
    return {index for index, row in enumerate(rows) if any(marker in cell for cell in row)}


class PlanPage(QWidget):
    """Страница генплана: вид с масштабированием и кнопкой «вписать»."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view = PlanView(self)
        fit = QPushButton("Вписать", self)
        zoom_in = QPushButton("+", self)
        zoom_out = QPushButton("−", self)
        fit.clicked.connect(self.view.fit)
        zoom_in.clicked.connect(lambda: self.view.zoom_by(1.25))
        zoom_out.clicked.connect(lambda: self.view.zoom_by(1 / 1.25))
        toolbar = QHBoxLayout()
        toolbar.addWidget(fit)
        toolbar.addWidget(zoom_in)
        toolbar.addWidget(zoom_out)
        toolbar.addStretch(1)
        layout = QVBoxLayout(self)
        layout.addLayout(toolbar)
        layout.addWidget(self.view, 1)
