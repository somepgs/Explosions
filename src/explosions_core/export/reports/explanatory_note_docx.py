"""Генератор расчетно-пояснительной записки склада ВМ (DOCX): фасад над разделами пакета `note`."""

from pathlib import Path

from explosions_core.domain import DetonationPairResult, UVVDistanceResult, WarehouseProjectInput
from explosions_core.calc.safe_distances import load_appendix11_tables
from explosions_core.export.reports.docx_styles import create_report_document
from explosions_core.export.reports.note.records import BermRecord, LightningRecord, StorageSizingRecord
from explosions_core.export.reports.note.section_checklist import add_section_8
from explosions_core.export.reports.note.sections_distances import add_section_4, add_section_5
from explosions_core.export.reports.note.sections_general import add_section_1, add_section_2, add_section_3, add_title_block
from explosions_core.export.reports.note.sections_protection import add_section_6, add_section_7

__all__ = [
    "BermRecord",
    "LightningRecord",
    "StorageSizingRecord",
    "export_explanatory_note_docx",
]


def export_explanatory_note_docx(
    project_input: WarehouseProjectInput,
    sizing_records: list[StorageSizingRecord],
    detonation_results: list[DetonationPairResult],
    uvv_results: list[UVVDistanceResult],
    berm_records: list[BermRecord],
    lightning_records: list[LightningRecord],
    output_path: Path,
    tables: dict | None = None,
) -> Path:
    tables = tables if tables is not None else load_appendix11_tables()
    doc = create_report_document()
    add_title_block(doc, project_input.name)
    add_section_1(doc)
    add_section_2(doc, project_input)
    add_section_3(doc, project_input, sizing_records)
    add_section_4(doc, project_input, detonation_results, tables)
    add_section_5(doc, project_input, uvv_results)
    add_section_6(doc, project_input, berm_records)
    add_section_7(doc, project_input, lightning_records)
    add_section_8(
        doc,
        project_input,
        sizing_records,
        detonation_results,
        uvv_results,
        berm_records,
        lightning_records,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)
    return output_path
