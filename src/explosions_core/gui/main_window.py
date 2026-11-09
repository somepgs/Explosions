"""Главное окно мастера: экран «Проекты» и восемь шагов, меню, расчет, сохранение и выгрузка (PySide6).

Окно не содержит расчетной логики. Данные шагов хранятся в общем `WizardData`, проверяются схемой
`ProjectDefinition` и передаются в `ProjectSession`. После каждого изменения (с задержкой) окно обновляет
значки ✔/⚠/✖ у шагов и выполняет предварительный расчет для промежуточных результатов шагов 2–5.
Предварительный расчет не записывается в историю базы данных.
"""

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from explosions_core.domain import ProjectCalculationResult, ProjectDefinition
from explosions_core.gui.dialogs import CHOICE_CALCULATE, CHOICE_CORRECT, DialogService
from explosions_core.gui.help_texts import WORKFLOW_TEXT, data_storage_text
from explosions_core.gui.precheck import (
    STEP_CALCULATION,
    STEP_LIGHTNING,
    STEP_PLACEMENT,
    STEP_PROJECT,
    STEP_SIZING,
    STEP_STORAGES,
    STEP_TARGETS,
    STEP_TERRITORY,
    ReadinessItem,
    check_readiness,
    has_blocking_errors,
    step_statuses,
)
from explosions_core.gui.projects_page import ProjectsPage
from explosions_core.gui.session import ProjectSession, ProjectSessionError
from explosions_core.gui.step_page import StepPage
from explosions_core.gui.steps import (
    CalculationStep,
    LightningStep,
    PlacementStep,
    ProjectStep,
    SizingStep,
    StepContent,
    StoragesStep,
    TargetsStep,
    TerritoryStep,
)
from explosions_core.gui.wizard import (
    FIRST_STEP,
    LAST_STEP,
    PROJECTS_PAGE_INDEX,
    STEP_BY_NUMBER,
    WIZARD_STEPS,
    navigation_row_to_step,
    navigation_titles,
    next_step,
    previous_step,
    step_to_navigation_row,
)
from explosions_core.gui.wizard_data import WizardData
from explosions_core.io.project_db import ProjectDatabaseError, default_database_path
from explosions_core.pipeline import calculate_project

APP_TITLE = "Склад ВМ: расчетное ядро"
PROJECT_FILTER = "Файлы проекта (*.json);;Все файлы (*)"
SETTINGS_ORG = "ExplosionsCore"
SETTINGS_APP = "ExplosionsGUI"
SETTINGS_LAST_DIR = "last_dir"
EXAMPLE_RELATIVE = Path("examples") / "demo_project.json"
LIVE_REFRESH_DELAY_MS = 400
STATUS_MARKS = {"error": "✖", "warning": "⚠", "info": "✔", None: "✔"}
STATUS_TOOLTIPS = {
    "error": "Есть ошибки: без исправления расчет не выполнится",
    "warning": "Есть предупреждения: данных не хватает для полной проверки",
    "info": "Заполнено (есть подсказки)",
    None: "Заполнено",
}
NOT_CALCULATED_MARK = "•"


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def example_path() -> Path | None:
    candidate = project_root() / EXAMPLE_RELATIVE
    return candidate if candidate.exists() else None


class ExportDialog(QDialog):
    """Выбор форматов выгрузки и папки результата."""

    def __init__(self, default_dir: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Выгрузка результатов")
        self._dxf = QCheckBox("Чертежи DXF (генплан и детальные чертежи хранилищ)", self)
        self._docx = QCheckBox("Пояснительная записка DOCX", self)
        self._json = QCheckBox("Результат расчета JSON", self)
        for box in (self._dxf, self._docx, self._json):
            box.setChecked(True)
        self._folder = QLabel(str(default_dir), self)
        self._folder.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Что выгрузить:", self))
        layout.addWidget(self._dxf)
        layout.addWidget(self._docx)
        layout.addWidget(self._json)
        layout.addWidget(QLabel("Папка результата:", self))
        layout.addWidget(self._folder)
        layout.addWidget(self._buttons)

    def formats(self) -> tuple[bool, bool, bool]:
        return self._dxf.isChecked(), self._docx.isChecked(), self._json.isChecked()


class MainWindow(QMainWindow):
    def __init__(
        self,
        session: ProjectSession | None = None,
        dialogs: DialogService | None = None,
        start_on_projects: bool = False,
    ) -> None:
        super().__init__()
        self._session = session if session is not None else ProjectSession()
        self._dialogs = dialogs if dialogs is not None else DialogService(self)
        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        self._data = WizardData(self._session.definition)
        self._preview_result: ProjectCalculationResult | None = None
        self._statuses: dict[int, str | None] = {}
        self._navigation = QListWidget(self)
        self._navigation.setMaximumWidth(250)
        self._navigation.addItems(navigation_titles())
        self._pages = QStackedWidget(self)
        self._projects_page = ProjectsPage(self)
        self._projects_page.set_database(self._session.database)
        self._projects_page.set_example_available(example_path() is not None)
        self._pages.addWidget(self._projects_page)
        self._contents: dict[int, StepContent] = {
            STEP_PROJECT: ProjectStep(self._data, self),
            STEP_STORAGES: StoragesStep(self._data, self),
            STEP_SIZING: SizingStep(self._data, self),
            STEP_PLACEMENT: PlacementStep(self._data, self),
            STEP_LIGHTNING: LightningStep(self._data, self),
            STEP_TERRITORY: TerritoryStep(self._data, self),
            STEP_TARGETS: TargetsStep(self._data, self),
            STEP_CALCULATION: CalculationStep(self._data, self),
        }
        self._step_pages: dict[int, StepPage] = {}
        self._build_step_pages()
        self._calc_step: CalculationStep = self._contents[STEP_CALCULATION]  # type: ignore[assignment]
        self._results_page = self._calc_step.results_page
        self._plan_page = self._calc_step.plan_page
        self._live_timer = QTimer(self)
        self._live_timer.setSingleShot(True)
        self._live_timer.setInterval(LIVE_REFRESH_DELAY_MS)
        self._live_timer.timeout.connect(self.refresh_live)
        self._connect_signals()
        central = QWidget(self)
        layout = QHBoxLayout(central)
        layout.addWidget(self._navigation)
        layout.addWidget(self._pages, 1)
        self.setCentralWidget(central)
        self._build_actions()
        self._build_menu()
        self._load_session_into_pages()
        start_row = PROJECTS_PAGE_INDEX if start_on_projects else step_to_navigation_row(FIRST_STEP)
        self._navigation.setCurrentRow(start_row)
        self._on_navigation_changed(start_row)
        self._update_title()
        self.resize(1360, 840)

    # ---------- построение ----------

    def _build_step_pages(self) -> None:
        for step in WIZARD_STEPS:
            page = StepPage(step.title, step.instruction, self)
            page.set_content(self._contents[step.number])
            page.back_requested.connect(self.go_back)
            page.next_requested.connect(self.go_next)
            page.set_back_enabled(step.number > FIRST_STEP)
            page.set_next_enabled(step.number < LAST_STEP)
            self._step_pages[step.number] = page
            self._pages.addWidget(page)

    def _connect_signals(self) -> None:
        self._navigation.currentRowChanged.connect(self._on_navigation_changed)
        for content in self._contents.values():
            content.changed.connect(self._on_data_changed)
        self._calc_step.calculate_requested.connect(self.calculate)
        self._calc_step.export_requested.connect(self.export_results)
        self._calc_step.step_requested.connect(self.go_to_step)
        self._projects_page.new_requested.connect(self.new_project)
        self._projects_page.open_requested.connect(self.open_project_id)
        self._projects_page.copy_requested.connect(self.copy_project_id)
        self._projects_page.delete_requested.connect(self.delete_project_id)
        self._projects_page.import_requested.connect(self.open_project)
        self._projects_page.example_requested.connect(self.open_example)

    def _build_actions(self) -> None:
        self._act_projects = QAction("Проекты", self, triggered=self.show_projects)
        self._act_new = QAction("Новый проект", self, shortcut=QKeySequence.StandardKey.New, triggered=self.new_project)
        self._act_open_db = QAction("Открыть из базы данных…", self, shortcut=QKeySequence.StandardKey.Open, triggered=self.open_from_database)
        self._act_save = QAction("Сохранить", self, shortcut=QKeySequence.StandardKey.Save, triggered=self.save_project)
        self._act_save_db = QAction("Сохранить в базу данных", self, triggered=self.save_to_database)
        self._act_open = QAction("Импорт проекта из JSON…", self, triggered=self.open_project)
        self._act_save_as = QAction("Экспорт проекта в JSON…", self, shortcut=QKeySequence.StandardKey.SaveAs, triggered=self.save_project_as)
        self._act_example = QAction("Открыть пример", self, triggered=self.open_example)
        self._act_calc = QAction("Рассчитать", self, shortcut=QKeySequence("F5"), triggered=self.calculate)
        self._act_check = QAction("Проверить данные", self, triggered=lambda: self.go_to_step(STEP_CALCULATION))
        self._act_export = QAction("Выгрузить результаты…", self, shortcut=QKeySequence("Ctrl+E"), triggered=self.export_results)
        self._act_workflow = QAction("Порядок работы", self, shortcut=QKeySequence("F1"), triggered=self.show_workflow)
        self._act_storage_info = QAction("Где хранятся данные", self, triggered=self.show_data_storage)
        self._act_about = QAction("О программе", self, triggered=self.about)
        self._act_example.setEnabled(example_path() is not None)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("Файл")
        for action in (self._act_projects, self._act_new, self._act_open_db):
            file_menu.addAction(action)
        file_menu.addSeparator()
        for action in (self._act_save, self._act_save_db):
            file_menu.addAction(action)
        file_menu.addSeparator()
        for action in (self._act_open, self._act_save_as, self._act_example):
            file_menu.addAction(action)
        file_menu.addSeparator()
        file_menu.addAction(self._act_export)
        calc_menu = self.menuBar().addMenu("Расчет")
        calc_menu.addAction(self._act_check)
        calc_menu.addAction(self._act_calc)
        help_menu = self.menuBar().addMenu("Справка")
        for action in (self._act_workflow, self._act_storage_info, self._act_about):
            help_menu.addAction(action)
        toolbar = self.addToolBar("Основные")
        toolbar.setMovable(False)
        for action in (self._act_projects, self._act_new, self._act_save, self._act_calc, self._act_export, self._act_workflow):
            toolbar.addAction(action)

    # ---------- навигация ----------

    def _on_navigation_changed(self, row: int) -> None:
        if row < 0:
            return
        self._pages.setCurrentIndex(row)
        step = navigation_row_to_step(row)
        if step is None:
            self._projects_page.refresh()
            return
        content = self._contents[step]
        content.load()
        content.show_preview(self._preview_result)

    def current_step(self) -> int | None:
        return navigation_row_to_step(self._navigation.currentRow())

    def navigation_titles(self) -> list[str]:
        return [self._navigation.item(row).text() for row in range(self._navigation.count())]

    def step_mark(self, step: int) -> str:
        return self._navigation.item(step_to_navigation_row(step)).text().split(" ", 1)[0]

    def go_to_step(self, step: int) -> None:
        self._navigation.setCurrentRow(step_to_navigation_row(step))

    def show_projects(self) -> None:
        self._navigation.setCurrentRow(PROJECTS_PAGE_INDEX)

    def go_next(self) -> None:
        step = self.current_step()
        if step is not None and next_step(step) is not None:
            self.go_to_step(next_step(step))

    def go_back(self) -> None:
        step = self.current_step()
        if step is not None and previous_step(step) is not None:
            self.go_to_step(previous_step(step))

    def step_content(self, step: int) -> StepContent:
        return self._contents[step]

    def step_page(self, step: int) -> StepPage:
        return self._step_pages[step]

    @property
    def projects_page(self) -> ProjectsPage:
        return self._projects_page

    def session(self) -> ProjectSession:
        return self._session

    # ---------- данные и живая проверка ----------

    def _load_session_into_pages(self) -> None:
        self._data.load(self._session.definition)
        self._results_page.clear()
        self._plan_page.view.set_data(self._session.definition.project, None)
        self.refresh_live()
        step = self.current_step()
        if step is not None:
            self._contents[step].load()
            self._contents[step].show_preview(self._preview_result)
        self._projects_page.refresh()

    def _on_data_changed(self) -> None:
        self._session.dirty = True
        self._session.result = None
        self._update_title()
        self._live_timer.start()

    def refresh_live(self) -> None:
        """Проверка готовности, значки шагов и предварительный расчет для промежуточных результатов."""
        self._live_timer.stop()
        schema_error: str | None = None
        items: list[ReadinessItem] = []
        result: ProjectCalculationResult | None = None
        try:
            definition = self._collect_definition()
        except ProjectSessionError as exc:
            definition = None
            schema_error = str(exc)
        if definition is not None:
            items = check_readiness(definition)
            try:
                result = calculate_project(definition)
            except Exception:  # noqa: BLE001 — предпросмотр не должен ронять окно, ошибки видны при расчете
                result = None
        self._preview_result = result
        self._statuses = step_statuses(items)
        if schema_error:
            current = self.current_step()
            if current is not None:
                self._statuses[current] = "error"
        self._update_navigation_marks()
        self._calc_step.set_readiness(items, schema_error)
        step = self.current_step()
        if step is not None:
            self._contents[step].show_preview(result)
        if schema_error:
            self.statusBar().showMessage(schema_error.splitlines()[-1] if schema_error else "", 8000)

    def _update_navigation_marks(self) -> None:
        for step in WIZARD_STEPS:
            item = self._navigation.item(step_to_navigation_row(step.number))
            level = self._statuses.get(step.number)
            if step.number == STEP_CALCULATION:
                mark = self._calculation_mark(level)
                tooltip = "Расчет не выполнен" if mark == NOT_CALCULATED_MARK else STATUS_TOOLTIPS.get(level, "")
            else:
                mark = STATUS_MARKS.get(level, "✔")
                tooltip = STATUS_TOOLTIPS.get(level, "")
            item.setText(f"{mark} {STEP_BY_NUMBER[step.number].title}")
            item.setToolTip(tooltip)

    def _calculation_mark(self, level: str | None) -> str:
        result = self._session.result
        if result is None:
            return STATUS_MARKS["error"] if level == "error" else NOT_CALCULATED_MARK
        return "✔" if result.is_compliant else "✖"

    def _collect_definition(self) -> ProjectDefinition:
        """Собирает общие данные шагов и проверяет их схемой проекта."""
        return self._data.definition()

    def _sync_session(self) -> bool:
        """Переносит данные шагов в сессию. Возвращает False и показывает ошибку, если данные неверны."""
        try:
            definition = self._collect_definition()
        except ProjectSessionError as exc:
            self._dialogs.show_error(APP_TITLE, str(exc))
            return False
        if definition != self._session.definition:
            self._session.replace_definition(definition)
        return True

    def _update_title(self) -> None:
        marker = " *" if self._session.dirty else ""
        self.setWindowTitle(f"{self._session.title}{marker} — {APP_TITLE}")

    def _last_dir(self) -> Path:
        stored = self._settings.value(SETTINGS_LAST_DIR, "")
        if stored and Path(str(stored)).exists():
            return Path(str(stored))
        return project_root()

    def _remember_dir(self, path: Path) -> None:
        self._settings.setValue(SETTINGS_LAST_DIR, str(path.parent))

    def _confirm_discard(self) -> bool:
        if not self._session.dirty:
            return True
        answer = QMessageBox.question(
            self,
            APP_TITLE,
            "Проект изменен. Сохранить изменения перед продолжением?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            return self.save_project()
        return True

    def _after_open(self) -> None:
        self._load_session_into_pages()
        self._update_title()
        self.go_to_step(FIRST_STEP)

    # ---------- проекты ----------

    def new_project(self) -> None:
        if not self._confirm_discard():
            return
        self._session.new_project()
        self._after_open()

    def open_project_id(self, project_id: int) -> bool:
        if not self._confirm_discard():
            return False
        try:
            self._session.open_from_database(project_id)
        except ProjectSessionError as exc:
            self._dialogs.show_error(APP_TITLE, str(exc))
            return False
        self._after_open()
        return True

    def copy_project_id(self, project_id: int) -> int | None:
        database = self._session.database
        if database is None:
            return None
        try:
            name = database.load_project(project_id).project.name
            new_id = database.duplicate_project(project_id, f"{name} (копия)")
        except ProjectDatabaseError as exc:
            self._dialogs.show_error(APP_TITLE, str(exc))
            return None
        self._projects_page.refresh()
        return new_id

    def delete_project_id(self, project_id: int) -> bool:
        database = self._session.database
        if database is None:
            return False
        name = next((r.name for r in database.list_projects() if r.id == project_id), str(project_id))
        if not self._dialogs.confirm(APP_TITLE, f"Удалить проект «{name}» и историю его расчетов из базы данных?"):
            return False
        try:
            database.delete_project(project_id)
        except ProjectDatabaseError as exc:
            self._dialogs.show_error(APP_TITLE, str(exc))
            return False
        if self._session.project_id == project_id:
            self._session.project_id = None
            self._session.dirty = True
            self._update_title()
        self._projects_page.refresh()
        return True

    def open_project(self) -> None:
        if not self._confirm_discard():
            return
        file_name, _ = QFileDialog.getOpenFileName(self, "Импорт проекта из JSON", str(self._last_dir()), PROJECT_FILTER)
        if not file_name:
            return
        self._open_path(Path(file_name))

    def open_example(self) -> None:
        if not self._confirm_discard():
            return
        path = example_path()
        if path is None:
            self._dialogs.show_error(APP_TITLE, "Файл примера не найден")
            return
        self._open_path(path)

    def _open_path(self, path: Path) -> bool:
        try:
            self._session.open(path)
        except ProjectSessionError as exc:
            self._dialogs.show_error(APP_TITLE, str(exc))
            return False
        self._remember_dir(path)
        self._after_open()
        return True

    def open_from_database(self) -> bool:
        if not self._confirm_discard():
            return False
        if self._session.database is None:
            self._dialogs.show_error(APP_TITLE, "База данных не подключена")
            return False
        try:
            records = self._session.database.list_projects()
        except ProjectDatabaseError as exc:
            self._dialogs.show_error(APP_TITLE, str(exc))
            return False
        if not records:
            self._dialogs.show_error(APP_TITLE, "В базе данных пока нет сохраненных проектов. Сохраните проект через «Файл → Сохранить в базу данных».")
            return False
        choice = self._dialogs.choose_project(records)
        if choice is None:
            return False
        try:
            self._session.open_from_database(choice)
        except ProjectSessionError as exc:
            self._dialogs.show_error(APP_TITLE, str(exc))
            return False
        self._after_open()
        return True

    def save_project(self) -> bool:
        """Ctrl+S: в базу данных, если она подключена и проект не открыт из файла; иначе в файл JSON."""
        if self._session.database is not None and self._session.path is None:
            return self.save_to_database()
        if not self._sync_session():
            return False
        if self._session.path is None:
            return self.save_project_as()
        return self._write(self._session.path)

    def save_to_database(self) -> bool:
        """Сохраняет проект в SQLite: создает запись или обновляет открытый проект из базы."""
        if not self._sync_session():
            return False
        try:
            project_id = self._session.save_to_database()
        except ProjectSessionError as exc:
            self._dialogs.show_error(APP_TITLE, f"Не удалось сохранить в базу данных: {exc}")
            return False
        self._update_title()
        self._projects_page.refresh()
        self.statusBar().showMessage(f"Проект сохранен в базу данных (номер {project_id})", 5000)
        return True

    def save_project_as(self) -> bool:
        if not self._sync_session():
            return False
        suggested = str(self._last_dir() / "project.json")
        file_name, _ = QFileDialog.getSaveFileName(self, "Экспорт проекта в JSON", suggested, PROJECT_FILTER)
        if not file_name:
            return False
        path = Path(file_name)
        if path.suffix.lower() != ".json":
            path = path.with_suffix(".json")
        return self._write(path)

    def _write(self, path: Path) -> bool:
        try:
            self._session.save(path)
        except (ProjectSessionError, OSError, ValueError) as exc:
            self._dialogs.show_error(APP_TITLE, f"Не удалось сохранить файл: {exc}")
            return False
        self._remember_dir(path)
        self._update_title()
        self.statusBar().showMessage(f"Сохранено: {path}", 5000)
        return True

    # ---------- расчет и выгрузка ----------

    def calculate(self) -> bool:
        if not self._sync_session():
            return False
        items = check_readiness(self._session.definition)
        self._calc_step.set_readiness(items)
        if items:
            choice, step = self._dialogs.ask_precheck(items)
            if choice == CHOICE_CORRECT:
                if step is not None:
                    self.go_to_step(step)
                return False
            if has_blocking_errors(items) or choice != CHOICE_CALCULATE:
                return False
        self.setCursor(Qt.CursorShape.WaitCursor)
        try:
            result = self._session.calculate()
        except ProjectSessionError as exc:
            self._dialogs.show_error(APP_TITLE, str(exc))
            return False
        finally:
            self.unsetCursor()
        self._preview_result = result
        self._results_page.show_result(result)
        self._plan_page.view.set_data(result.project, result)
        self._update_navigation_marks()
        self.go_to_step(STEP_CALCULATION)
        self._calc_step.show_results_tab()
        self.statusBar().showMessage("Расчет выполнен", 5000)
        self._dialogs.show_summary(result)
        return True

    def export_results(self) -> bool:
        if not self.calculate():
            return False
        default_dir = self._last_dir()
        dialog = ExportDialog(default_dir, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        dxf, docx, json_result = dialog.formats()
        if not (dxf or docx or json_result):
            self._dialogs.show_error(APP_TITLE, "Не выбран ни один формат выгрузки")
            return False
        folder = self._choose_export_folder(default_dir)
        if folder is None:
            return False
        try:
            written = self._session.export(folder, dxf=dxf, docx=docx, json_result=json_result)
        except (ProjectSessionError, OSError, ValueError) as exc:
            self._dialogs.show_error(APP_TITLE, f"Выгрузка не выполнена: {exc}")
            return False
        self.statusBar().showMessage(f"Выгружено файлов: {len(written)}", 8000)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        return True

    def _choose_export_folder(self, default_dir: Path) -> Path | None:
        folder = QFileDialog.getExistingDirectory(self, "Папка для результатов", str(default_dir))
        return Path(folder) if folder else None

    # ---------- справка ----------

    def database_path(self) -> Path:
        return self._session.database.path if self._session.database is not None else default_database_path()

    def show_workflow(self) -> None:
        self._dialogs.show_info("Порядок работы", WORKFLOW_TEXT)

    def show_data_storage(self) -> None:
        self._dialogs.show_info("Где хранятся данные", data_storage_text(self.database_path()))

    def about(self) -> None:
        self._dialogs.show_info(
            "О программе",
            "Расчетное ядро проектирования складов ВМ по Приказу МИР РК № 343 (ред. 02.10.2025).\n"
            "Работает локально, без сетевых портов. Результаты требуют проверки инженером.",
        )

    def closeEvent(self, event) -> None:  # noqa: N802 (имя из Qt)
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()
