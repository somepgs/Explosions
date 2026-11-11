"""Выгрузка всех выходных файлов расчета проекта: генплан, чертежи хранилищ, записка и JSON результата."""

import re
from pathlib import Path

from explosions_core.domain import ProjectCalculationResult
from explosions_core.export.cad.master_plan_dxf import export_master_plan_dxf
from explosions_core.export.cad.storage_detail_dxf import export_storage_detail_dxf
from explosions_core.export.reports.explanatory_note_docx import export_explanatory_note_docx
from explosions_core.io.project_file import save_calculation_result

MASTER_PLAN_FILE_NAME = "master_plan_safety_zones.dxf"
NOTE_FILE_NAME = "explanatory_note.docx"
RESULT_FILE_NAME = "calculation_result.json"
SAFE_NAME_PATTERN = re.compile(r"[^\w\-]+")


def export_project_outputs(
    result: ProjectCalculationResult,
    out_dir: Path,
    *,
    dxf: bool = True,
    docx: bool = True,
    json_result: bool = True,
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    if dxf:
        written.append(_export_master_plan(result, out_dir))
        written.extend(_export_storage_details(result, out_dir))
    if docx:
        written.append(_export_note(result, out_dir))
    if json_result:
        written.append(save_calculation_result(result, out_dir / RESULT_FILE_NAME))
    return written


def _export_master_plan(result: ProjectCalculationResult, out_dir: Path) -> Path:
    return export_master_plan_dxf(
        result.project,
        result.detonation_results,
        result.uvv_results,
        result.berm_results_by_storage,
        out_dir / MASTER_PLAN_FILE_NAME,
    )


def _export_storage_details(result: ProjectCalculationResult, out_dir: Path) -> list[Path]:
    berms = {record.storage_id: record for record in result.berm_records}
    lightnings = {record.storage_id: record for record in result.lightning_records}
    written: list[Path] = []
    for sizing in result.sizing_records:
        berm = berms.get(sizing.storage_id)
        lightning = lightnings.get(sizing.storage_id)
        if berm is None or lightning is None:
            continue
        path = out_dir / f"storage_detail_{_safe_name(sizing.storage_id)}.dxf"
        written.append(
            export_storage_detail_dxf(
                sizing.sizing_input,
                sizing.result,
                berm.berm_input,
                berm.result,
                lightning.masts,
                lightning.result,
                path,
                wall_thickness_m=result.settings.wall_thickness_m,
            )
        )
    return written


def _export_note(result: ProjectCalculationResult, out_dir: Path) -> Path:
    return export_explanatory_note_docx(
        result.project,
        result.sizing_records,
        result.detonation_results,
        result.uvv_results,
        result.berm_records,
        result.lightning_records,
        out_dir / NOTE_FILE_NAME,
    )


def _safe_name(storage_id: str) -> str:
    return SAFE_NAME_PATTERN.sub("_", storage_id).strip("_") or "storage"
