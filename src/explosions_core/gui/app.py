"""Точка входа GUI: `python -m explosions_core.gui [файл_проекта.json]` или `explosions-gui`.

Без аргумента окно открывается на экране «Проекты» (список из базы SQLite в профиле пользователя).
С файлом JSON — проект импортируется и открывается шаг 1.
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from explosions_core.gui.main_window import APP_TITLE, MainWindow
from explosions_core.gui.session import ProjectSession, ProjectSessionError
from explosions_core.io.project_db import ProjectDatabase, ProjectDatabaseError, default_database_path

STYLE = "Fusion"


def open_default_database(path: Path | None = None) -> ProjectDatabase | None:
    """База проектов по умолчанию; при ошибке доступа — None (работа с файлами JSON остается)."""
    try:
        return ProjectDatabase(path if path is not None else default_database_path())
    except ProjectDatabaseError as exc:
        print(f"База данных проектов недоступна: {exc}", file=sys.stderr)
        return None


def build_window(project_file: Path | None = None, database: ProjectDatabase | None = None) -> MainWindow:
    """Окно с открытым файлом проекта; без файла — стартовый экран «Проекты»."""
    session = ProjectSession(database=database)
    if project_file is not None:
        session.open(project_file)
    return MainWindow(session, start_on_projects=project_file is None)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName(APP_TITLE)
    app.setStyle(STYLE)
    project_file = Path(args[0]) if args else None
    try:
        window = build_window(project_file, open_default_database())
    except ProjectSessionError as exc:
        print(f"Не удалось открыть проект: {exc}", file=sys.stderr)
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
