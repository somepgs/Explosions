"""Сессия проекта для интерфейса: открыть, изменить, сохранить, рассчитать, выгрузить (без Qt)."""

from pathlib import Path

from pydantic import ValidationError

from explosions_core.domain import (
    CalculationSettings,
    LocationType,
    ProjectCalculationResult,
    ProjectDefinition,
    StorageBuilding,
    WarehouseCategory,
    WarehouseDuration,
    WarehouseProjectInput,
)
from explosions_core.export.project_export import export_project_outputs
from explosions_core.gui.labels import format_validation_error
from explosions_core.io.project_db import ProjectDatabase, ProjectDatabaseError
from explosions_core.io.project_file import load_project_file, save_project_file
from explosions_core.pipeline import calculate_project

NEW_PROJECT_NAME = "Новый склад ВМ"
TEMPLATE_STORAGE_ID = "S1"
TEMPLATE_STORAGE_NAME = "Хранилище 1"


class ProjectSessionError(Exception):
    """Понятная пользователю ошибка сессии (текст выводится в диалоге)."""


def new_definition() -> ProjectDefinition:
    """Пустой проект с одним хранилищем-шаблоном: заполняется пользователем в формах."""
    storage = StorageBuilding(
        name=TEMPLATE_STORAGE_NAME,
        storage_id=TEMPLATE_STORAGE_ID,
        category=WarehouseCategory.BASIS,
        duration=WarehouseDuration.PERMANENT,
        location_type=LocationType.SURFACE,
    )
    return ProjectDefinition(project=WarehouseProjectInput(name=NEW_PROJECT_NAME, storages=[storage]))


def definition_from_dict(data: dict) -> ProjectDefinition:
    """Проверка словаря, собранного из форм, той же схемой, что и файл проекта."""
    try:
        return ProjectDefinition.model_validate(data)
    except ValidationError as exc:
        raise ProjectSessionError(format_validation_error(exc)) from exc


class ProjectSession:
    """Состояние открытого проекта: определение, путь к файлу или номер в базе, признак изменений и результат."""

    def __init__(
        self,
        definition: ProjectDefinition | None = None,
        path: Path | None = None,
        database: ProjectDatabase | None = None,
    ) -> None:
        self.definition: ProjectDefinition = definition if definition is not None else new_definition()
        self.path: Path | None = path
        self.database: ProjectDatabase | None = database
        self.project_id: int | None = None
        self.dirty: bool = False
        self.result: ProjectCalculationResult | None = None

    @property
    def title(self) -> str:
        if self.path is not None:
            return self.path.name
        if self.project_id is not None:
            return self.definition.project.name
        return "Без имени"

    def new_project(self) -> None:
        self.definition = new_definition()
        self.path = None
        self.project_id = None
        self.dirty = False
        self.result = None

    def require_database(self) -> ProjectDatabase:
        if self.database is None:
            raise ProjectSessionError("База данных не подключена")
        return self.database

    def save_to_database(self) -> int:
        """Создает запись проекта в базе или обновляет открытый проект."""
        database = self.require_database()
        try:
            if self.project_id is None:
                self.project_id = database.create_project(self.definition)
            else:
                database.save_project(self.project_id, self.definition)
        except ProjectDatabaseError as exc:
            raise ProjectSessionError(str(exc)) from exc
        self.dirty = False
        return self.project_id

    def open_from_database(self, project_id: int) -> None:
        database = self.require_database()
        try:
            definition = database.load_project(project_id)
        except ProjectDatabaseError as exc:
            raise ProjectSessionError(str(exc)) from exc
        self.definition = definition
        self.path = None
        self.project_id = project_id
        self.dirty = False
        self.result = None

    def open(self, path: Path) -> None:
        try:
            definition = load_project_file(path)
        except Exception as exc:
            raise ProjectSessionError(str(exc)) from exc
        self.definition = definition
        self.path = path
        self.project_id = None
        self.dirty = False
        self.result = None

    def replace_definition(self, definition: ProjectDefinition) -> None:
        self.definition = definition
        self.dirty = True
        self.result = None

    def save(self, path: Path | None = None) -> Path:
        target = path if path is not None else self.path
        if target is None:
            raise ProjectSessionError("Укажите имя файла для сохранения проекта")
        saved = save_project_file(self.definition, target)
        self.path = saved
        self.dirty = False
        return saved

    def calculate(self) -> ProjectCalculationResult:
        try:
            result = calculate_project(self.definition)
        except ValueError as exc:
            self.result = None
            raise ProjectSessionError(f"Расчет невозможен: {exc}") from exc
        self.result = result
        if self.database is not None and self.project_id is not None:
            try:
                self.database.add_calculation(self.project_id, result)
            except ProjectDatabaseError as exc:
                raise ProjectSessionError(f"Расчет выполнен, но история не сохранена: {exc}") from exc
        return result

    def export(
        self,
        out_dir: Path,
        *,
        dxf: bool = True,
        docx: bool = True,
        json_result: bool = True,
    ) -> list[Path]:
        if self.result is None:
            raise ProjectSessionError("Сначала выполните расчет")
        return export_project_outputs(self.result, out_dir, dxf=dxf, docx=docx, json_result=json_result)

    def settings(self) -> CalculationSettings:
        return self.definition.settings
