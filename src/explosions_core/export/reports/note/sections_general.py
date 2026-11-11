"""Титул, раздел 1 (НПА), раздел 2 (исходные данные, совместимость) и раздел 3 (планировка хранилищ)."""

import math

from docx.enum.text import WD_ALIGN_PARAGRAPH

from explosions_core.norms.constants_rk343 import (
    MAX_PALLET_TIERS_COUNT,
    MAX_RACK_SHELF_HEIGHT_OTHER_M,
    MAX_RACK_SHELF_HEIGHT_UNSEALED_BC_M,
    MAX_RACK_WIDTH_UNITS_ISLAND,
    MAX_RACK_WIDTH_UNITS_WALL,
    MAX_STACK_HEIGHT_PALLET_M,
    MAX_STACK_HEIGHT_STANDARD_M,
    MAX_STACK_WIDTH_UNITS,
    MIN_CEILING_CLEARANCE_ABOVE_LOAD_M,
    MIN_SHELF_VERTICAL_GAP_M,
    MIN_WALL_CLEARANCE_M,
)
from explosions_core.domain import (
    BermSoilMaterial,
    CompatibilityGroup,
    LocationType,
    PackagingType,
    StorageMethod,
    WarehouseCategory,
    WarehouseDuration,
    WarehouseProjectInput,
)
from explosions_core.calc.safe_distances import calculate_tnt_equivalent_mass
from explosions_core.export.reports.docx_styles import (
    add_heading,
    add_paragraph,
    add_red_bold_paragraph,
    add_rich_text,
    add_table,
)
from explosions_core.export.reports.note.common import (
    add_step,
    add_violations,
    cmp_sign,
    fmt,
    storage_index,
)
from explosions_core.export.reports.note.records import StorageSizingRecord
from explosions_core.norms.references import (
    CLAUSE_COMPATIBILITY,
    CLAUSE_COMPATIBILITY_EXCEPTION,
    CLAUSE_RACK,
    CLAUSE_STACK,
    NPA_LIST,
)
from explosions_core.validators.compatibility import check_storage_compatibility

CATEGORY_LABELS = {WarehouseCategory.BASIS: "основной склад", WarehouseCategory.EXPENDABLE: "расходный склад"}
DURATION_LABELS = {
    WarehouseDuration.PERMANENT: "постоянный",
    WarehouseDuration.TEMPORARY: "временный",
    WarehouseDuration.SHORT_TERM: "кратковременный",
    WarehouseDuration.MOBILE: "передвижной",
}
LOCATION_LABELS = {
    LocationType.SURFACE: "наземное",
    LocationType.SEMI_BURIED: "полузаглубленное",
    LocationType.BURIED: "заглубленное",
    LocationType.UNDERGROUND: "подземное",
}
SOIL_LABELS = {
    BermSoilMaterial.PLASTIC_CLAY_LOAM: "пластичный грунт (глина, суглинок)",
    BermSoilMaterial.SANDY_FREE_FLOWING: "сыпучий грунт (песок, супесь)",
    BermSoilMaterial.STONE_OR_GRAVEL: "камень, щебень",
    BermSoilMaterial.COMBUSTIBLE_MATERIAL: "горючие материалы, угольная мелочь",
}


def add_title_block(doc, project_name: str) -> None:
    for text, bold in (
        ("РАСЧЕТНО-ПОЯСНИТЕЛЬНАЯ ЗАПИСКА", True),
        (f"к проекту склада ВМ: {project_name}", False),
    ):
        paragraph = doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_rich_text(paragraph, text, bold=bold)


def add_section_1(doc) -> None:
    add_heading(doc, "1. Нормативно-правовая база проектирования", level=1)
    add_paragraph(
        doc,
        "Основной нормативный документ: Приказ МИР РК от 30.12.2014 № 343 (далее — Приказ № 343). Расчеты также "
        "выполнены по смежным нормативным правовым актам Республики Казахстан. Перечень НПА:",
    )
    for index, npa in enumerate(NPA_LIST, start=1):
        add_paragraph(doc, f"{index}) {npa}")


def add_section_2(doc, project: WarehouseProjectInput) -> None:
    add_heading(doc, "2. Исходные данные, классификация склада и проверка совместимости ВМ", level=1)
    add_paragraph(doc, "Таблица 2.1 — Общие характеристики проектируемого склада ВМ", bold=True)
    add_table(
        doc,
        ["Хранилище", "Категория склада", "Срок эксплуатации", "Расположение"],
        [
            [s.name, CATEGORY_LABELS[s.category], DURATION_LABELS[s.duration], LOCATION_LABELS[s.location_type]]
            for s in project.storages
        ],
    )
    add_paragraph(doc, "Таблица 2.2 — Номенклатура, масса, тротиловый эквивалент и группы совместимости ВМ", bold=True)
    rows: list[list[str]] = []
    for storage in project.storages:
        for item in storage.items:
            k_teq = item.tnt_equivalent_coeff
            if k_teq is None:
                rows.append(
                    [
                        storage.name,
                        item.name,
                        item.hazard_subclass or "—",
                        item.group.value,
                        fmt(item.mass_kg),
                        "не задан",
                        "не определен",
                    ]
                )
                continue
            rows.append(
                [
                    storage.name,
                    item.name,
                    item.hazard_subclass or "—",
                    item.group.value,
                    fmt(item.mass_kg),
                    fmt(k_teq),
                    fmt(item.mass_kg * k_teq),
                ]
            )
    add_table(doc, ["Хранилище", "ВМ", "Подкласс", "Группа", "Q, кг", "K_тэ", "Q_тэ, кг"], rows)

    for storage in project.storages:
        missing = [item.name for item in storage.items if item.tnt_equivalent_coeff is None]
        if missing:
            add_red_bold_paragraph(
                doc,
                f"Хранилище «{storage.name}»: не задан коэффициент K_тэ для партий {', '.join(missing)}; "
                "Q_тэ по ним не определен и в расчет не включен",
            )
        total = calculate_tnt_equivalent_mass(storage.items, skip_missing=True)
        parts = [
            f"{fmt(item.mass_kg)} · {fmt(item.tnt_equivalent_coeff)}"
            for item in storage.items
            if item.tnt_equivalent_coeff is not None
        ] or ["0"]
        add_step(
            doc,
            f"Эквивалентная масса хранилища «{storage.name}»",
            "Q_{тэ} = Σ Q_{i} · K_{тэ,i}",
            f"Q_{{тэ}} = {' + '.join(parts)} = {fmt(total)} кг",
            f"Q_{{тэ}} = {fmt(total)} кг ({fmt(total / 1000.0, 3)} т)",
            ok=not missing,
        )
        compatibility = check_storage_compatibility(storage)
        groups = sorted({item.group.value for item in storage.items})
        conclusion = (
            f"группы не конфликтуют, совместное хранение в «{storage.name}» допустимо "
            f"({CLAUSE_COMPATIBILITY}; {CLAUSE_COMPATIBILITY_EXCEPTION})"
            if compatibility.is_valid
            else f"в «{storage.name}» смешаны несовместимые группы; раздельное хранение обязательно "
            f"({CLAUSE_COMPATIBILITY})"
        )
        add_step(
            doc,
            f"Совместимость ВМ в хранилище «{storage.name}»",
            "N_{гр} = число различных групп G_{i};  N_{гр} ≤ 1 (исключения п. 9: дымный порох D с бездымным C; "
            "группа G с B, C, D; детонирующий шнур D с детонаторами B)",
            f"N_{{гр}} = {len(groups)} ({', '.join(groups) if groups else '—'})",
            conclusion,
            ok=compatibility.is_valid,
        )
        add_violations(doc, compatibility.violations)


def _add_sizing_steps(doc, project: WarehouseProjectInput, record: StorageSizingRecord) -> None:
    storage_name = storage_index(project)[record.storage_id].name
    data = record.sizing_input
    result = record.result
    spec = data.unit_spec
    ok = not result.violations
    add_paragraph(doc, f"Хранилище «{storage_name}»", bold=True)

    add_step(
        doc,
        "Число грузовых мест тары",
        "N_{мест} = ⌈Q_{общ} / m_{нетто.ед}⌉",
        f"N_{{мест}} = ⌈{fmt(data.total_net_explosive_mass_kg)} / {fmt(spec.net_weight_kg)}⌉ = "
        f"⌈{fmt(data.total_net_explosive_mass_kg / spec.net_weight_kg)}⌉ = {result.total_units_required} шт.",
        f"принято {result.total_units_required} мест, масса брутто {fmt(result.total_gross_weight_kg)} кг",
        ok=ok,
    )

    if data.storage_method == StorageMethod.RACK:
        unsealed_bc = data.is_unsealed and (
            data.compatibility_group in (CompatibilityGroup.B, CompatibilityGroup.C) or data.is_black_powder
        )
        top_limit = MAX_RACK_SHELF_HEIGHT_UNSEALED_BC_M if unsealed_bc else MAX_RACK_SHELF_HEIGHT_OTHER_M
        step = result.shelf_step_height_m or 0.0
        add_step(
            doc,
            "Вертикальный шаг полок стеллажа",
            "H_{шага} = n_{ярусов} · h_{места} + Δ_{зазора} + t_{полки}",
            f"H_{{шага}} = {result.tiers_per_shelf} · {fmt(spec.height_m)} + {fmt(data.shelf_vertical_gap_m)} + "
            f"{fmt(data.shelf_thickness_m)} = {fmt(step)} м",
            f"полок {result.shelves_or_tiers_count}; верхняя полка {fmt(result.top_shelf_height_m or 0.0)} м "
            f"{cmp_sign(result.top_shelf_height_m or 0.0, top_limit, at_most=True)} {fmt(top_limit)} м, зазор "
            f"{fmt(data.shelf_vertical_gap_m)} м {cmp_sign(data.shelf_vertical_gap_m, MIN_SHELF_VERTICAL_GAP_M, at_most=False)} "
            f"{fmt(MIN_SHELF_VERTICAL_GAP_M)} м ({CLAUSE_RACK})",
            ok=ok,
        )
    else:
        max_h = (
            MAX_STACK_HEIGHT_PALLET_M
            if data.packaging_type in (PackagingType.PALLET, PackagingType.CONTAINER)
            else MAX_STACK_HEIGHT_STANDARD_M
        )
        raw_tiers = (max_h - data.floor_deck_height_m) / spec.height_m
        floor_tiers = math.floor(raw_tiers + 1e-9)
        if data.packaging_type in (PackagingType.PALLET, PackagingType.CONTAINER):
            formula = "n_{ярусов} = min(2; ⌊(H_{max} − h_{настила}) / h_{места}⌋)"
            substitution = (
                f"n_{{ярусов}} = min({MAX_PALLET_TIERS_COUNT}; ⌊({fmt(max_h)} − {fmt(data.floor_deck_height_m)}) / "
                f"{fmt(spec.height_m)}⌋) = min({MAX_PALLET_TIERS_COUNT}; {floor_tiers}) = {result.shelves_or_tiers_count}"
            )
        else:
            formula = "n_{ярусов} = ⌊(H_{max} − h_{настила}) / h_{места}⌋"
            substitution = (
                f"n_{{ярусов}} = ⌊({fmt(max_h)} − {fmt(data.floor_deck_height_m)}) / {fmt(spec.height_m)}⌋ = "
                f"{result.shelves_or_tiers_count}"
            )
        add_step(
            doc,
            "Число ярусов штабеля и высота от пола",
            formula,
            substitution,
            f"H_{{загр}} = {fmt(data.floor_deck_height_m)} + {result.shelves_or_tiers_count} · "
            f"{fmt(spec.height_m)} = {fmt(result.total_loaded_height_m)} м "
            f"{cmp_sign(result.total_loaded_height_m, max_h, at_most=True)} {fmt(max_h)} м ({CLAUSE_STACK})",
            ok=ok,
        )

    if data.storage_method == StorageMethod.RACK:
        wall_count = data.wall_racks_count
        total_lines = wall_count + data.island_rows_count
        add_step(
            doc,
            "Вместимость поперечного сечения и длина линии",
            "N_{сеч} = n_{полок} · n_{ярусов} · (N_{стен} · 1 + N_{остр} · 2);  L_{лин} = n_{дл} · l_{места} + (n_{дл} − 1) · δ",
            f"N_{{сеч}} = {result.shelves_or_tiers_count} · {result.tiers_per_shelf} · ({wall_count} · "
            f"{MAX_RACK_WIDTH_UNITS_WALL} + {data.island_rows_count} · {MAX_RACK_WIDTH_UNITS_ISLAND}) = "
            f"{result.units_per_cross_section};  n_{{дл}} = ⌈{result.total_units_required} / "
            f"{result.units_per_cross_section}⌉ = {result.units_along_line};  L_{{лин}} = {fmt(result.line_length_m)} м",
            f"линий {total_lines}, по длине {result.units_along_line} мест",
            ok=ok,
        )
    else:
        width_units = 1 if data.packaging_type == PackagingType.CONTAINER else MAX_STACK_WIDTH_UNITS
        add_step(
            doc,
            "Вместимость поперечного сечения и длина линии штабелей",
            "N_{сеч} = n_{ярусов} · N_{ширина} · N_{линий};  n_{дл} = ⌈N_{мест} / N_{сеч}⌉;  L_{лин} = n_{дл} · l_{места} + (n_{дл} − 1) · δ",
            f"N_{{сеч}} = {result.shelves_or_tiers_count} · {width_units} · {data.island_rows_count} = "
            f"{result.units_per_cross_section};  n_{{дл}} = ⌈{result.total_units_required} / "
            f"{result.units_per_cross_section}⌉ = {result.units_along_line};  L_{{лин}} = {result.units_along_line} · "
            f"{fmt(spec.length_m)} + {max(0, result.units_along_line - 1)} · {fmt(spec.unit_gap_m)} = "
            f"{fmt(result.line_length_m)} м",
            f"{data.island_rows_count} линии штабелей, по длине {result.units_along_line} мест, "
            f"длина линии {fmt(result.line_length_m)} м",
            ok=ok,
        )

    wall_count = data.wall_racks_count if data.storage_method == StorageMethod.RACK else 0
    island_count = data.island_rows_count
    longitudinal = max(1, wall_count + island_count - 1)
    b_aisle = result.required_aisle_width_m
    add_step(
        doc,
        "Минимальная внутренняя ширина хранилища",
        "W_{внутр} = 2 · c_{стен} + N_{стен} · b_{стен} + N_{остр} · b_{остр} + n_{пр} · b_{пр}",
        f"W_{{внутр}} = 2 · {fmt(data.wall_clearance_m)} + {wall_count} · {fmt(result.wall_rack_depth_m)} + "
        f"{island_count} · {fmt(result.island_line_depth_m)} + {longitudinal} · {fmt(b_aisle)} = "
        f"{fmt(result.min_internal_width_m)} м",
        f"W_{{внутр}} = {fmt(result.min_internal_width_m)} м; отступ {fmt(data.wall_clearance_m)} м "
        f"{cmp_sign(data.wall_clearance_m, MIN_WALL_CLEARANCE_M, at_most=False)} {fmt(MIN_WALL_CLEARANCE_M)} м, "
        f"проход {fmt(b_aisle)} м (п. 579–580)",
        ok=ok,
    )
    add_step(
        doc,
        "Минимальная внутренняя длина хранилища",
        "L_{внутр} = 2 · c_{стен} + L_{лин} + n_{торц} · b_{пр}",
        f"L_{{внутр}} = 2 · {fmt(data.wall_clearance_m)} + {fmt(result.line_length_m)} + "
        f"{data.cross_aisles_count} · {fmt(b_aisle)} = {fmt(result.min_internal_length_m)} м",
        f"L_{{внутр}} = {fmt(result.min_internal_length_m)} м",
        ok=ok,
    )
    add_step(
        doc,
        "Минимальная внутренняя высота помещения",
        "H_{внутр} = H_{загр} + Δ_{потолка}",
        f"H_{{внутр}} = {fmt(result.total_loaded_height_m)} + {fmt(MIN_CEILING_CLEARANCE_ABOVE_LOAD_M)} = "
        f"{fmt(result.min_internal_height_m)} м",
        f"H_{{внутр}} = {fmt(result.min_internal_height_m)} м с запасом над верхним ярусом",
        ok=ok,
    )
    add_violations(doc, result.violations)


def add_section_3(doc, project: WarehouseProjectInput, sizing_records: list[StorageSizingRecord]) -> None:
    add_heading(doc, "3. Расчет внутренней планировки, количества стеллажей (штабелей) и габаритов хранилищ", level=1)
    for record in sizing_records:
        _add_sizing_steps(doc, project, record)
    names = storage_index(project)
    add_paragraph(doc, "Таблица 3.1 — Сводная ведомость габаритных и технологических параметров хранилищ ВМ", bold=True)
    add_table(
        doc,
        ["Хранилище", "Мест тары, шт.", "Ярусов/полок", "H_загр, м", "W_внутр, м", "L_внутр, м", "H_внутр, м"],
        [
            [
                names[record.storage_id].name,
                str(record.result.total_units_required),
                str(record.result.shelves_or_tiers_count),
                fmt(record.result.total_loaded_height_m),
                fmt(record.result.min_internal_width_m),
                fmt(record.result.min_internal_length_m),
                fmt(record.result.min_internal_height_m),
            ]
            for record in sizing_records
        ],
    )
