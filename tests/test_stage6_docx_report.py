from pathlib import Path

import docx
from docx.oxml.ns import qn

from explosions_core.export.reports.docx_styles import RED
from explosions_core.export.reports.explanatory_note_docx import export_explanatory_note_docx
from tests.fixtures.sample_project import build_sample_note_data

SECTION_PREFIXES = tuple(f"{number}. " for number in range(1, 9))


def _export(tmp_path: Path, clear_distance_m: float | None = None) -> Path:
    data = build_sample_note_data() if clear_distance_m is None else build_sample_note_data(clear_distance_m)
    output = tmp_path / "explanatory_note.docx"
    export_explanatory_note_docx(
        data.project,
        data.sizing_records,
        data.detonation_results,
        data.uvv_results,
        data.berm_records,
        data.lightning_records,
        output,
    )
    return output


def _all_text(document: docx.document.Document) -> str:
    parts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return "\n".join(parts)


def _red_bold_texts(document: docx.document.Document) -> list[str]:
    result: list[str] = []
    for paragraph in document.paragraphs:
        for run in paragraph.runs:
            if run.bold and run.font.color.rgb == RED and run.text.strip():
                result.append(run.text)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        if run.bold and run.font.color.rgb == RED and run.text.strip():
                            result.append(run.text)
    return result


def test_report_contains_all_eight_sections(tmp_path: Path) -> None:
    document = docx.Document(_export(tmp_path))
    headings = [p.text for p in document.paragraphs if p.style.name == "Heading 1"]
    assert len(headings) == 8
    for prefix, heading in zip(SECTION_PREFIXES, headings):
        assert heading.startswith(prefix)


def test_report_contains_at_least_seven_tables(tmp_path: Path) -> None:
    document = docx.Document(_export(tmp_path))
    assert len(document.tables) >= 7


def test_report_contains_exact_numeric_substitutions(tmp_path: Path) -> None:
    text = _all_text(docx.Document(_export(tmp_path)))
    assert "80.00" in text
    assert "15.53" in text
    assert "7.34" in text


def test_report_cites_required_normative_references(tmp_path: Path) -> None:
    text = _all_text(docx.Document(_export(tmp_path)))
    for reference in (
        "Приказ МИР РК от 30.12.2014 № 343",
        "п. 579",
        "п. 603",
        "СП РК 2.04-103-2013",
    ):
        assert reference in text


def test_page_is_a4_with_gost_margins(tmp_path: Path) -> None:
    section = docx.Document(_export(tmp_path)).sections[0]
    assert round(section.page_width.mm) == 210
    assert round(section.page_height.mm) == 297
    assert round(section.left_margin.mm) == 25
    assert round(section.right_margin.mm) == 10
    assert round(section.top_margin.mm) == 20
    assert round(section.bottom_margin.mm) == 20


def test_normal_and_heading_styles_use_times_new_roman(tmp_path: Path) -> None:
    document = docx.Document(_export(tmp_path))
    for style_name in ("Normal", "Heading 1", "Heading 2", "Heading 3"):
        rfonts = document.styles[style_name].element.rPr.rFonts
        for attribute in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            assert rfonts.get(qn(attribute)) == "Times New Roman"


def test_table_header_is_shaded_with_d9e1f2(tmp_path: Path) -> None:
    document = docx.Document(_export(tmp_path))
    header_cell = document.tables[0].rows[0].cells[0]
    shading = header_cell._tc.tcPr.find(qn("w:shd"))
    assert shading is not None
    assert shading.get(qn("w:fill")) == "D9E1F2"


def test_formulas_use_subscript_and_superscript_runs(tmp_path: Path) -> None:
    document = docx.Document(_export(tmp_path))
    runs = [run for paragraph in document.paragraphs for run in paragraph.runs]
    assert any(run.font.subscript for run in runs)
    assert any(run.text == "д" and run.font.subscript for run in runs)


def test_normal_report_has_no_red_violation_text(tmp_path: Path) -> None:
    document = docx.Document(_export(tmp_path))
    assert _red_bold_texts(document) == []


def test_violation_is_marked_red_bold(tmp_path: Path) -> None:
    document = docx.Document(_export(tmp_path, clear_distance_m=35.0))
    red_texts = _red_bold_texts(document)
    assert any("DETONATION_TRANSFER_DISTANCE" in text for text in red_texts)
    assert any("п. 15" in text or "Приложения 11" in text for text in _all_text(document).split("\n") if text)
