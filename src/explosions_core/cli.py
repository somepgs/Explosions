"""Командная строка расчетного ядра: `calc` — полный расчет проекта, `validate` — проверка файла проекта.

Коды выхода: 0 — нарушений и ошибок расчета нет; 1 — ошибка входных данных или файла;
2 — расчет выполнен, но есть нарушения нормативов или ошибки модулей.
"""

import argparse
import sys
from pathlib import Path

from explosions_core import __version__
from explosions_core.domain import NormativeViolation, ProjectCalculationResult, ProjectDefinition
from explosions_core.export.project_export import export_project_outputs
from explosions_core.io.project_file import ProjectFileError, load_project_file
from explosions_core.pipeline import calculate_project

EXIT_OK = 0
EXIT_INPUT_ERROR = 1
EXIT_NONCOMPLIANT = 2
DEFAULT_OUT_DIR = Path("output_project")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="explosions-core", description="Расчетное ядро склада ВМ (Приказ МИР РК № 343)")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    calc = subparsers.add_parser("calc", help="выполнить расчет проекта и при необходимости выгрузить файлы")
    calc.add_argument("project", type=Path, help="путь к файлу проекта .json")
    calc.add_argument("--dxf", action="store_true", help="выгрузить чертежи DXF")
    calc.add_argument("--docx", action="store_true", help="выгрузить расчетно-пояснительную записку DOCX")
    calc.add_argument("--json", dest="json_result", action="store_true", help="сохранить результат расчета JSON")
    calc.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR, help="папка для выходных файлов")

    validate = subparsers.add_parser("validate", help="проверить файл проекта на соответствие схеме")
    validate.add_argument("project", type=Path, help="путь к файлу проекта .json")
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_console()
    args = build_parser().parse_args(argv)
    try:
        definition = load_project_file(args.project)
    except ProjectFileError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_INPUT_ERROR

    if args.command == "validate":
        print(f"Файл проекта корректен: {args.project}")
        print(f"Хранилищ: {len(definition.project.storages)}, проектных разделов: {len(definition.storage_designs)}")
        return EXIT_OK

    return _run_calc(definition, args)


def _run_calc(definition: ProjectDefinition, args: argparse.Namespace) -> int:
    try:
        result = calculate_project(definition)
    except ValueError as exc:
        print(f"Ошибка данных проекта: {exc}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    _print_summary(result)
    if args.dxf or args.docx or args.json_result:
        written = export_project_outputs(
            result,
            args.out,
            dxf=args.dxf,
            docx=args.docx,
            json_result=args.json_result,
        )
        print("Выходные файлы:")
        for path in written:
            print(f"  {path}")
    return EXIT_OK if result.is_compliant else EXIT_NONCOMPLIANT


def _print_summary(result: ProjectCalculationResult) -> None:
    print(f"Проект: {result.project.name}")
    print(f"Хранилищ: {len(result.project.storages)}")
    print(f"Пар по передаче детонации: {len(result.detonation_results)}, проверок по УВВ: {len(result.uvv_results)}")
    _print_violations(result.all_violations)
    if result.issues:
        print("Замечания расчета:")
        for issue in result.issues:
            label = "ОШИБКА" if issue.severity == "error" else "предупреждение"
            where = f" [{issue.object_id}]" if issue.object_id else ""
            print(f"  {label} ({issue.module}){where}: {issue.message}")
    verdict = "соответствует нормативам" if result.is_compliant else "НЕ соответствует нормативам или расчет неполный"
    print(f"Итог: {verdict}")


def _print_violations(violations: list[NormativeViolation]) -> None:
    if not violations:
        print("Нарушения нормативов: нет")
        return
    print(f"Нарушения нормативов: {len(violations)}")
    for violation in violations:
        print(f"  [{violation.code}] {violation.description} — {violation.clause}")


def _configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")


if __name__ == "__main__":
    sys.exit(main())
