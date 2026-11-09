"""Файл проекта (JSON, utf-8) и сохранение результатов расчета."""

from pathlib import Path

from pydantic import ValidationError

from explosions_core.domain import ProjectCalculationResult, ProjectDefinition

PROJECT_FILE_ENCODING = "utf-8"
JSON_INDENT = 2


class ProjectFileError(Exception):
    """Файл проекта не удалось прочитать или он не соответствует схеме."""


def load_project_file(path: Path) -> ProjectDefinition:
    if not path.is_file():
        raise ProjectFileError(f"Файл проекта не найден: {path}")
    text = path.read_text(encoding=PROJECT_FILE_ENCODING)
    try:
        return ProjectDefinition.model_validate_json(text)
    except ValidationError as exc:
        raise ProjectFileError(_format_validation_error(path, exc)) from exc


def save_project_file(definition: ProjectDefinition, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(definition.model_dump_json(indent=JSON_INDENT), encoding=PROJECT_FILE_ENCODING)
    return path


def save_calculation_result(result: ProjectCalculationResult, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.model_dump_json(indent=JSON_INDENT), encoding=PROJECT_FILE_ENCODING)
    return path


def _format_validation_error(path: Path, exc: ValidationError) -> str:
    lines = [f"Файл проекта не соответствует схеме: {path}"]
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "<корень>"
        lines.append(f"  {location}: {error['msg']}")
    return "\n".join(lines)
