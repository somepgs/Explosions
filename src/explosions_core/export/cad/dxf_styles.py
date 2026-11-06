"""Настройка DXF-документа, слоев, текстовых и размерных стилей и вспомогательных примитивов (ГОСТ 2.303-68, ГОСТ 21.508-2020)."""

import math
from dataclasses import dataclass
from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment
from ezdxf.document import Drawing

DXF_VERSION = "R2010"
INSUNITS_METERS = 6
MEASUREMENT_METRIC = 1
TEXT_STYLE_NAME = "GOST_TEXT"
TEXT_FONT = "arial.ttf"
DIM_STYLE_NAME = "GOST_M"
DIM_BASE_STYLE = "EZDXF"
WALL_THICKNESS_M = 0.40
MAST_MARK_RADIUS_M = 0.3
TEXT_HEIGHT_M = 0.3
TITLE_TEXT_HEIGHT_M = 0.6
DIM_TEXT_HEIGHT_M = 0.3
DIM_ARROW_SIZE_M = 0.2
DIM_EXTENSION_M = 0.2
DIM_OFFSET_M = 0.2
SLOPE_TICK_STEP_M = 1.0


@dataclass(frozen=True)
class LayerSpec:
    name: str
    color: int
    linetype: str
    lineweight: int


LAYER_WALLS = "01_STORAGE_WALLS"
LAYER_RACKS = "02_RACKS_AND_STACKS"
LAYER_AISLES = "03_INTERNAL_AISLES"
LAYER_BERM_CREST = "04_BERM_CREST"
LAYER_BERM_TOE = "05_BERM_TOE_AND_SLOPES"
LAYER_LIGHTNING = "06_LIGHTNING_PROTECTION"
LAYER_PERIMETER = "07_PERIMETER_AND_ZONES"
LAYER_SAFE_RD = "08_SAFE_RADIUS_RD"
LAYER_SAFE_UVV = "09_SAFE_RADIUS_UVV"
LAYER_DIMENSIONS = "10_DIMENSIONS_AND_TEXT"

LAYERS: tuple[LayerSpec, ...] = (
    LayerSpec(LAYER_WALLS, 7, "CONTINUOUS", 50),
    LayerSpec(LAYER_RACKS, 4, "CONTINUOUS", 30),
    LayerSpec(LAYER_AISLES, 8, "DASHED", 18),
    LayerSpec(LAYER_BERM_CREST, 32, "CONTINUOUS", 35),
    LayerSpec(LAYER_BERM_TOE, 30, "CONTINUOUS", 18),
    LayerSpec(LAYER_LIGHTNING, 5, "DASHDOT", 25),
    LayerSpec(LAYER_PERIMETER, 3, "PHANTOM", 30),
    LayerSpec(LAYER_SAFE_RD, 6, "DASHED", 35),
    LayerSpec(LAYER_SAFE_UVV, 1, "CENTER", 50),
    LayerSpec(LAYER_DIMENSIONS, 2, "CONTINUOUS", 18),
)


def create_document(ltscale: float = 1.0) -> Drawing:
    doc = ezdxf.new(dxfversion=DXF_VERSION, setup=True)
    doc.header["$INSUNITS"] = INSUNITS_METERS
    doc.header["$MEASUREMENT"] = MEASUREMENT_METRIC
    doc.header["$LWDISPLAY"] = 1
    doc.header["$LTSCALE"] = ltscale
    doc.styles.add(TEXT_STYLE_NAME, font=TEXT_FONT)
    _setup_dimstyle(doc)
    for spec in LAYERS:
        doc.layers.add(spec.name, color=spec.color, linetype=spec.linetype, lineweight=spec.lineweight)
    return doc


def _setup_dimstyle(doc: Drawing) -> None:
    doc.dimstyles.duplicate_entry(DIM_BASE_STYLE, DIM_STYLE_NAME)
    dimstyle = doc.dimstyles.get(DIM_STYLE_NAME)
    dimstyle.dxf.dimtxsty = TEXT_STYLE_NAME
    dimstyle.dxf.dimtxt = DIM_TEXT_HEIGHT_M
    dimstyle.dxf.dimasz = DIM_ARROW_SIZE_M
    dimstyle.dxf.dimexe = DIM_EXTENSION_M
    dimstyle.dxf.dimexo = DIM_OFFSET_M
    dimstyle.dxf.dimdle = 0.0
    dimstyle.dxf.dimlfac = 1.0


def save_document(doc: Drawing, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(output_path, encoding="utf-8")
    return output_path


def add_rectangle(msp, x1: float, y1: float, x2: float, y2: float, layer: str):
    points = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    return msp.add_lwpolyline(points, close=True, dxfattribs={"layer": layer})


def add_polyline(msp, points: list[tuple[float, float]], layer: str, close: bool = False):
    return msp.add_lwpolyline(points, close=close, dxfattribs={"layer": layer})


def add_circle(msp, center: tuple[float, float], radius: float, layer: str):
    return msp.add_circle(center, radius, dxfattribs={"layer": layer})


def add_text(msp, text: str, position: tuple[float, float], layer: str, height: float = TEXT_HEIGHT_M):
    entity = msp.add_text(text, height=height, dxfattribs={"layer": layer, "style": TEXT_STYLE_NAME})
    entity.set_placement(position, align=TextEntityAlignment.MIDDLE_LEFT)
    return entity


def add_mtext(
    msp,
    text: str,
    position: tuple[float, float],
    layer: str,
    char_height: float = TEXT_HEIGHT_M,
    width: float | None = None,
):
    attribs = {"layer": layer, "char_height": char_height, "style": TEXT_STYLE_NAME}
    if width is not None:
        attribs["width"] = width
    entity = msp.add_mtext(text, dxfattribs=attribs)
    entity.set_location(position)
    return entity


def add_filled_circle(msp, center: tuple[float, float], radius: float, layer: str, segments: int = 32):
    hatch = msp.add_hatch(color=7, dxfattribs={"layer": layer})
    hatch.set_solid_fill()
    vertices = [
        (center[0] + radius * math.cos(2 * math.pi * k / segments), center[1] + radius * math.sin(2 * math.pi * k / segments))
        for k in range(segments)
    ]
    hatch.paths.add_polyline_path(vertices, is_closed=True)
    return hatch


def add_cross_marker(msp, center: tuple[float, float], half_size: float, layer: str) -> None:
    x, y = center
    msp.add_line((x - half_size, y), (x + half_size, y), dxfattribs={"layer": layer})
    msp.add_line((x, y - half_size), (x, y + half_size), dxfattribs={"layer": layer})


def add_arrow(msp, tip: tuple[float, float], direction_deg: float, length_m: float, layer: str) -> None:
    angle = math.radians(direction_deg)
    back_x = tip[0] - length_m * math.cos(angle)
    back_y = tip[1] - length_m * math.sin(angle)
    half = length_m / 3.0
    side_x = -math.sin(angle) * half
    side_y = math.cos(angle) * half
    base_left = (back_x + side_x, back_y + side_y)
    base_right = (back_x - side_x, back_y - side_y)
    add_polyline(msp, [tip, base_left, base_right], layer, close=True)


def add_linear_dimension(
    msp,
    p1: tuple[float, float],
    p2: tuple[float, float],
    base: tuple[float, float],
    layer: str = LAYER_DIMENSIONS,
    text: str | None = None,
    angle: float = 0.0,
):
    attribs = {"layer": layer}
    dim = msp.add_linear_dim(
        base=base,
        p1=p1,
        p2=p2,
        angle=angle,
        text=text if text is not None else "<>",
        dimstyle=DIM_STYLE_NAME,
        dxfattribs=attribs,
    )
    dim.render()
    return dim


def add_aligned_dimension(
    msp,
    p1: tuple[float, float],
    p2: tuple[float, float],
    distance: float,
    layer: str = LAYER_DIMENSIONS,
    text: str | None = None,
):
    dim = msp.add_aligned_dim(
        p1=p1,
        p2=p2,
        distance=distance,
        text=text if text is not None else "<>",
        dimstyle=DIM_STYLE_NAME,
        dxfattribs={"layer": layer},
    )
    dim.render()
    return dim


def draw_table(
    msp,
    origin: tuple[float, float],
    column_widths: list[float],
    rows: list[list[str]],
    row_height: float,
    layer: str = LAYER_DIMENSIONS,
    text_height: float = TEXT_HEIGHT_M,
) -> None:
    x0, y0 = origin
    total_width = sum(column_widths)
    total_height = row_height * len(rows)
    for row_index in range(len(rows) + 1):
        y = y0 - row_index * row_height
        msp.add_line((x0, y), (x0 + total_width, y), dxfattribs={"layer": layer})
    x = x0
    for width in [0.0, *column_widths]:
        x += width
        msp.add_line((x, y0), (x, y0 - total_height), dxfattribs={"layer": layer})
    for row_index, row in enumerate(rows):
        y_center = y0 - row_index * row_height - row_height / 2.0
        x_cell = x0
        for column_index, cell in enumerate(row):
            add_text(msp, cell, (x_cell + 0.1, y_center), layer, height=text_height)
            x_cell += column_widths[column_index]


def draw_slope_berm_ticks(
    msp,
    crest_p1: tuple[float, float],
    crest_p2: tuple[float, float],
    toe_p1: tuple[float, float],
    toe_p2: tuple[float, float],
    step_m: float = SLOPE_TICK_STEP_M,
    layer: str = LAYER_BERM_TOE,
) -> int:
    ux, uy = crest_p2[0] - crest_p1[0], crest_p2[1] - crest_p1[1]
    crest_length = math.hypot(ux, uy)
    if crest_length == 0.0:
        raise ValueError("Линия бровки вала имеет нулевую длину")
    ux, uy = ux / crest_length, uy / crest_length
    nx, ny = -uy, ux
    offset_x, offset_y = toe_p1[0] - crest_p1[0], toe_p1[1] - crest_p1[1]
    if offset_x * nx + offset_y * ny < 0.0:
        nx, ny = -nx, -ny
    width = abs(offset_x * nx + offset_y * ny)
    if width == 0.0:
        raise ValueError("Линии бровки и подошвы вала совпадают")

    tick_count = 0
    position = 0.0
    while position <= crest_length + 1e-9:
        start_x = crest_p1[0] + ux * position
        start_y = crest_p1[1] + uy * position
        ratio = 1.0 if tick_count % 2 == 0 else 0.5
        end_x = start_x + nx * width * ratio
        end_y = start_y + ny * width * ratio
        msp.add_line((start_x, start_y), (end_x, end_y), dxfattribs={"layer": layer})
        tick_count += 1
        position += step_m
    return tick_count
