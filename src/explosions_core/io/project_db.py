"""Файловая база данных SQLite (stdlib sqlite3): проекты склада ВМ и история расчетов. Без Qt."""

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from explosions_core.domain import ProjectCalculationResult, ProjectDefinition

DATABASE_FILE_NAME = "projects.sqlite3"
APP_DIR_NAME = "ExplosionsCore"
SCHEMA_VERSION = 1
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS calculations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    is_compliant INTEGER NOT NULL,
    violations_count INTEGER NOT NULL,
    errors_count INTEGER NOT NULL,
    warnings_count INTEGER NOT NULL,
    result_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_calculations_project ON calculations(project_id);
"""


class ProjectDatabaseError(Exception):
    """База данных недоступна, повреждена или запись не найдена. Текст выводится пользователю."""


@dataclass(frozen=True)
class ProjectRecord:
    id: int
    name: str
    updated_at: str


@dataclass(frozen=True)
class CalculationRecord:
    id: int
    project_id: int
    created_at: str
    is_compliant: bool
    violations_count: int
    errors_count: int
    warnings_count: int


def default_database_path() -> Path:
    """Локальная папка пользователя (не сетевая): %LOCALAPPDATA%\\ExplosionsCore\\projects.sqlite3."""
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / "AppData" / "Local"
    return root / APP_DIR_NAME / DATABASE_FILE_NAME


def _now() -> str:
    return datetime.now().strftime(DATE_FORMAT)


class ProjectDatabase:
    """Хранилище проектов и истории расчетов. Каждый вызов открывает короткое соединение."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(self.path)
        except sqlite3.Error as exc:
            raise ProjectDatabaseError(f"Не удалось открыть базу данных {self.path}: {exc}") from exc
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ProjectDatabaseError(f"Не удалось создать папку для базы данных {self.path.parent}: {exc}") from exc
        connection = self._connect()
        try:
            with connection:
                connection.executescript(SCHEMA_SQL)
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        except sqlite3.Error as exc:
            raise ProjectDatabaseError(f"База данных повреждена или недоступна ({self.path}): {exc}") from exc
        finally:
            connection.close()

    def _run(self, action):
        connection = self._connect()
        try:
            with connection:
                return action(connection)
        except sqlite3.Error as exc:
            raise ProjectDatabaseError(f"Ошибка базы данных: {exc}") from exc
        finally:
            connection.close()

    def list_projects(self) -> list[ProjectRecord]:
        def action(connection: sqlite3.Connection) -> list[ProjectRecord]:
            rows = connection.execute("SELECT id, name, updated_at FROM projects ORDER BY updated_at DESC, id DESC")
            return [ProjectRecord(id=row["id"], name=row["name"], updated_at=row["updated_at"]) for row in rows]

        return self._run(action)

    def create_project(self, definition: ProjectDefinition) -> int:
        now = _now()

        def action(connection: sqlite3.Connection) -> int:
            cursor = connection.execute(
                "INSERT INTO projects (name, schema_version, definition_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (definition.project.name, definition.schema_version, definition.model_dump_json(), now, now),
            )
            return int(cursor.lastrowid)

        return self._run(action)

    def load_project(self, project_id: int) -> ProjectDefinition:
        def action(connection: sqlite3.Connection) -> str | None:
            row = connection.execute("SELECT definition_json FROM projects WHERE id = ?", (project_id,)).fetchone()
            return None if row is None else row["definition_json"]

        text = self._run(action)
        if text is None:
            raise ProjectDatabaseError(f"Проект с номером {project_id} не найден в базе данных")
        try:
            return ProjectDefinition.model_validate_json(text)
        except ValueError as exc:
            raise ProjectDatabaseError(f"Данные проекта {project_id} повреждены: {exc}") from exc

    def save_project(self, project_id: int, definition: ProjectDefinition) -> None:
        def action(connection: sqlite3.Connection) -> int:
            cursor = connection.execute(
                "UPDATE projects SET name = ?, schema_version = ?, definition_json = ?, updated_at = ? WHERE id = ?",
                (
                    definition.project.name,
                    definition.schema_version,
                    definition.model_dump_json(),
                    _now(),
                    project_id,
                ),
            )
            return cursor.rowcount

        if self._run(action) == 0:
            raise ProjectDatabaseError(f"Проект с номером {project_id} не найден в базе данных")

    def duplicate_project(self, project_id: int, new_name: str) -> int:
        definition = self.load_project(project_id)
        copy = definition.model_copy(update={"project": definition.project.model_copy(update={"name": new_name})})
        return self.create_project(copy)

    def delete_project(self, project_id: int) -> None:
        def action(connection: sqlite3.Connection) -> int:
            cursor = connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            return cursor.rowcount

        if self._run(action) == 0:
            raise ProjectDatabaseError(f"Проект с номером {project_id} не найден в базе данных")

    def add_calculation(self, project_id: int, result: ProjectCalculationResult) -> int:
        warnings_count = sum(1 for issue in result.issues if issue.severity == "warning")

        def action(connection: sqlite3.Connection) -> int:
            cursor = connection.execute(
                "INSERT INTO calculations (project_id, created_at, is_compliant, violations_count, "
                "errors_count, warnings_count, result_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    project_id,
                    _now(),
                    int(result.is_compliant),
                    len(result.all_violations),
                    len(result.errors),
                    warnings_count,
                    result.model_dump_json(),
                ),
            )
            return int(cursor.lastrowid)

        return self._run(action)

    def list_calculations(self, project_id: int) -> list[CalculationRecord]:
        def action(connection: sqlite3.Connection) -> list[CalculationRecord]:
            rows = connection.execute(
                "SELECT id, project_id, created_at, is_compliant, violations_count, errors_count, warnings_count "
                "FROM calculations WHERE project_id = ? ORDER BY id DESC",
                (project_id,),
            )
            return [
                CalculationRecord(
                    id=row["id"],
                    project_id=row["project_id"],
                    created_at=row["created_at"],
                    is_compliant=bool(row["is_compliant"]),
                    violations_count=row["violations_count"],
                    errors_count=row["errors_count"],
                    warnings_count=row["warnings_count"],
                )
                for row in rows
            ]

        return self._run(action)

    def backup(self, target: Path) -> Path:
        """Копия базы данных средствами SQLite (консистентна даже при открытом соединении)."""
        target.parent.mkdir(parents=True, exist_ok=True)
        source = self._connect()
        destination = sqlite3.connect(target)
        try:
            source.backup(destination)
        except sqlite3.Error as exc:
            raise ProjectDatabaseError(f"Не удалось создать копию базы данных: {exc}") from exc
        finally:
            destination.close()
            source.close()
        return target
