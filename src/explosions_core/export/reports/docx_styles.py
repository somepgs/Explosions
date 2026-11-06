"""Стили DOCX-записки: А4, поля по ГОСТ 21.101-2020, кириллические шрифты Times New Roman, таблицы и формулы."""

import re

from docx import Document
from docx.document import Document as DocumentType
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor
from docx.table import Table
from docx.text.paragraph import Paragraph

PAGE_WIDTH_MM = 210
PAGE_HEIGHT_MM = 297
MARGIN_LEFT_MM = 25
MARGIN_RIGHT_MM = 10
MARGIN_TOP_MM = 20
MARGIN_BOTTOM_MM = 20
FONT_NAME = "Times New Roman"
BODY_SIZE_PT = 12
TABLE_SIZE_PT = 10
TABLE_HEADER_FILL = "D9E1F2"
HEADING_STYLES = ("Heading 1", "Heading 2", "Heading 3")
BLACK = RGBColor(0x00, 0x00, 0x00)
RED = RGBColor(0xC0, 0x00, 0x00)
_MARKUP = re.compile(r"(_\{[^{}]*\}|\^\{[^{}]*\})")
_THEME_ATTRIBUTES = ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme")
_FONT_ATTRIBUTES = ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia")


def _apply_font(rpr_owner) -> None:
    rfonts = rpr_owner.get_or_add_rPr().get_or_add_rFonts()
    for attribute in _THEME_ATTRIBUTES:
        key = qn(attribute)
        if key in rfonts.attrib:
            del rfonts.attrib[key]
    for attribute in _FONT_ATTRIBUTES:
        rfonts.set(qn(attribute), FONT_NAME)


def create_report_document() -> DocumentType:
    doc = Document()
    section = doc.sections[0]
    section.page_width = Mm(PAGE_WIDTH_MM)
    section.page_height = Mm(PAGE_HEIGHT_MM)
    section.left_margin = Mm(MARGIN_LEFT_MM)
    section.right_margin = Mm(MARGIN_RIGHT_MM)
    section.top_margin = Mm(MARGIN_TOP_MM)
    section.bottom_margin = Mm(MARGIN_BOTTOM_MM)

    normal = doc.styles["Normal"]
    normal.font.size = Pt(BODY_SIZE_PT)
    normal.font.color.rgb = BLACK
    _apply_font(normal.element)

    for name in HEADING_STYLES:
        style = doc.styles[name]
        style.font.size = Pt(BODY_SIZE_PT)
        style.font.bold = True
        style.font.color.rgb = BLACK
        _apply_font(style.element)
    return doc


def add_run(
    paragraph: Paragraph,
    text: str,
    *,
    bold: bool = False,
    subscript: bool = False,
    superscript: bool = False,
    size_pt: float = BODY_SIZE_PT,
    color: RGBColor | None = None,
):
    run = paragraph.add_run(text)
    run.bold = bold
    run.font.subscript = subscript
    run.font.superscript = superscript
    run.font.size = Pt(size_pt)
    run.font.color.rgb = color if color is not None else BLACK
    _apply_font(run._r)
    return run


def add_rich_text(
    paragraph: Paragraph,
    text: str,
    *,
    bold: bool = False,
    size_pt: float = BODY_SIZE_PT,
    color: RGBColor | None = None,
) -> Paragraph:
    for piece in _MARKUP.split(text):
        if not piece:
            continue
        if piece.startswith("_{"):
            add_run(paragraph, piece[2:-1], bold=bold, subscript=True, size_pt=size_pt, color=color)
        elif piece.startswith("^{"):
            add_run(paragraph, piece[2:-1], bold=bold, superscript=True, size_pt=size_pt, color=color)
        else:
            add_run(paragraph, piece, bold=bold, size_pt=size_pt, color=color)
    return paragraph


def add_heading(doc: DocumentType, text: str, level: int = 1) -> Paragraph:
    return doc.add_heading(text, level=level)


def add_paragraph(doc: DocumentType, text: str, *, bold: bool = False, color: RGBColor | None = None) -> Paragraph:
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.first_line_indent = Mm(12)
    return add_rich_text(paragraph, text, bold=bold, color=color)


def add_formula(doc: DocumentType, formula: str) -> Paragraph:
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return add_rich_text(paragraph, formula)


def add_red_bold_paragraph(doc: DocumentType, text: str) -> Paragraph:
    return add_paragraph(doc, text, bold=True, color=RED)


def _shade_cell(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:val"), "clear")
    shading.set(qn("w:color"), "auto")
    shading.set(qn("w:fill"), fill)
    tc_pr.append(shading)


def _fill_cell(cell, text: str, *, bold: bool, color: RGBColor | None, fill: str | None) -> None:
    paragraph = cell.paragraphs[0]
    add_rich_text(paragraph, text, bold=bold, size_pt=TABLE_SIZE_PT, color=color)
    if fill is not None:
        _shade_cell(cell, fill)


def add_table(
    doc: DocumentType,
    headers: list[str],
    rows: list[list[str]],
    red_rows: frozenset[int] = frozenset(),
) -> Table:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = doc.styles["Table Grid"]
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for cell, header in zip(table.rows[0].cells, headers):
        _fill_cell(cell, header, bold=True, color=None, fill=TABLE_HEADER_FILL)
    for index, row in enumerate(rows):
        is_red = index in red_rows
        cells = table.add_row().cells
        for cell, value in zip(cells, row):
            _fill_cell(cell, value, bold=is_red, color=RED if is_red else None, fill=None)
    doc.add_paragraph()
    return table
