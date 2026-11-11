"""Реестр источников нормативных констант.

Для каждой константы `constants_rk343` указаны пункт-источник и статус сверки с PDF в Documentation:
Приказ МИР РК № 343 (ред. от 02.10.2025) с Приложениями, СП РК 2.04-103-2013, СО 153-34.21.122-2003,
РД 34.21.122-87, ПУЭ РК (Приказ МЭ РК № 230).
- VERIFIED — значение найдено в тексте PDF и совпадает;
- DESIGN_DEFAULT — проектное значение по умолчанию (задания разработки или решение инженера), не норматив;
- NO_SOURCE_TEXT — в имеющихся текстах такой нормы нет (значение из задания разработки, требует решения инженера).
"""

from typing import Final, Literal

Status = Literal["verified", "design_default", "no_source_text"]
VERIFIED: Final[Status] = "verified"
DESIGN_DEFAULT: Final[Status] = "design_default"
NO_SOURCE_TEXT: Final[Status] = "no_source_text"

CONSTANT_SOURCES: Final[dict[str, tuple[str, Status]]] = {
    "MIN_FORBIDDEN_ZONE_WIDTH_M": ("п. 590, подпункт 5", VERIFIED),
    "MIN_FENCE_HEIGHT_PERMANENT_M": ("п. 593", VERIFIED),
    "MIN_FENCE_HEIGHT_TEMPORARY_M": ("п. 618, подпункт 3", VERIFIED),
    "MIN_FENCE_HEIGHT_SHORT_TERM_M": ("п. 621", VERIFIED),
    "MIN_DIST_FENCE_TO_STORAGE_M": ("п. 593", VERIFIED),
    "MIN_DIST_FENCE_TO_GUARDHOUSE_M": ("п. 592 (за запретной зоной) и п. 590, подпункт 5 (50 м)", VERIFIED),
    "MIN_DIST_FENCE_TO_TARE_STORAGE_M": ("п. 592", VERIFIED),
    "MIN_OPEN_FIRE_BAN_RADIUS_M": ("п. 16", VERIFIED),
    "MIN_DIST_FENCE_TO_STORAGE_SHORT_TERM_M": ("п. 621", VERIFIED),
    "MIN_DIST_FENCE_TO_GUARDHOUSE_SHORT_TERM_M": ("п. 621", VERIFIED),
    "MIN_WALL_CLEARANCE_M": ("п. 579", VERIFIED),
    "MIN_FLOOR_DECK_HEIGHT_M": ("п. 579", VERIFIED),
    "MIN_AISLE_WIDTH_STACK_M": ("п. 579", VERIFIED),
    "MIN_AISLE_WIDTH_RACK_M": ("п. 579", VERIFIED),
    "MAX_STACK_HEIGHT_STANDARD_M": ("п. 579", VERIFIED),
    "MAX_STACK_HEIGHT_PALLET_M": ("п. 579", VERIFIED),
    "MAX_RACK_SHELF_HEIGHT_UNSEALED_BC_M": ("п. 580", VERIFIED),
    "MAX_TIERS_UNSEALED_BC": ("п. 580", VERIFIED),
    "MAX_RACK_SHELF_HEIGHT_OTHER_M": ("п. 580", VERIFIED),
    "MAX_TIERS_OTHER": ("п. 580", VERIFIED),
    "MIN_PRP_FENCE_DIST_M": ("п. 48, подпункт 1", VERIFIED),
    "MIN_PRP_FENCE_HEIGHT_M": ("п. 48, подпункт 1", VERIFIED),
    "MIN_PRP_SWITCH_DIST_M": ("п. 48, подпункт 2", VERIFIED),
    "MAX_PRP_GUARDHOUSE_DIST_M": ("п. 48, подпункт 4", VERIFIED),
    "MAX_MOBILE_PAYLOAD_RATIO": ("п. 74, подпункт 1", VERIFIED),
    "MIN_MOBILE_POWDER_SEPARATION_M": ("п. 74, подпункт 4", VERIFIED),
    "MIN_SHELF_VERTICAL_GAP_M": ("п. 580", VERIFIED),
    "MAX_SHELF_BOARD_GAP_M": ("п. 580", VERIFIED),
    "MAX_STACK_WIDTH_UNITS": ("п. 579", VERIFIED),
    "MAX_RACK_WIDTH_UNITS_ISLAND": ("п. 580", VERIFIED),
    "MAX_RACK_WIDTH_UNITS_WALL": ("п. 580", VERIFIED),
    "MAX_PALLET_TIERS_COUNT": ("п. 579", VERIFIED),
    "MIN_CEILING_CLEARANCE_ABOVE_LOAD_M": ("задание № 2", DESIGN_DEFAULT),
    "DEFAULT_UNIT_GAP_M": ("задание № 2", DESIGN_DEFAULT),
    "DEFAULT_SHELF_THICKNESS_M": ("задание № 2", DESIGN_DEFAULT),
    "UVV_FORMULA_MASS_OPEN_THRESHOLD_KG": ("Приложение 11, таблица 2", VERIFIED),
    "UVV_FORMULA_MASS_BURIED_THRESHOLD_KG": ("Приложение 11, таблица 2", VERIFIED),
    "UVV_TABLE3_FORMULA_SWITCH_KG": ("Приложение 11, таблица 3 (формулы в шапке строк)", VERIFIED),
    "DEFAULT_STACK_WIDTH_B_M": ("Приложение 11, таблица 5 и примеры п. 21", VERIFIED),
    "MIN_TOPOGRAPHY_REDUCTION_COEFF": ("Приложение 11, п. 10, подпункт 3", VERIFIED),
    "MAX_TOPOGRAPHY_REDUCTION_COEFF": ("Приложение 11, п. 10, подпункт 3", VERIFIED),
    "MIN_BERM_CREST_WIDTH_M": ("п. 604", VERIFIED),
    "MIN_BERM_CREST_ELEVATION_ABOVE_LOAD_M": ("п. 604", VERIFIED),
    "DEFAULT_CREST_ELEVATION_ABOVE_LOAD_M": ("п. 604 (принят минимум)", VERIFIED),
    "DEFAULT_BERM_SLOPE_ANGLE_DEG": ("задание № 4 (п. 604: по углу естественного откоса грунта)", DESIGN_DEFAULT),
    "MIN_BERM_SLOPE_ANGLE_DEG": ("задание № 4", DESIGN_DEFAULT),
    "MAX_BERM_SLOPE_ANGLE_DEG": ("задание № 4", DESIGN_DEFAULT),
    "DEFAULT_WALL_TO_TOE_CLEARANCE_M": ("задание № 4", DESIGN_DEFAULT),
    "DEFAULT_ENTRANCE_OPENING_WIDTH_M": ("задание № 4", DESIGN_DEFAULT),
    "DEFAULT_SCREEN_OVERLAP_M": ("задание № 4 (п. 605 проверяется расчетом)", DESIGN_DEFAULT),
    "MAX_ROD_ARRESTER_HEIGHT_M": ("СО 153-34.21.122-2003, п. 3.3.2.1 (формулы табл. 3.4 пригодны до 150 м)", VERIFIED),
    "MIN_ARRESTER_CLEARANCE_FROM_STORAGE_WALL_M": (
        "задание № 4 (нормы нет в СП РК, СО 153, РД 34.21.122-87 и ПУЭ РК: РД, п. 2.3 задает Sв = 3–4 м и более "
        "по сопротивлению грунта, заземлителю и высоте; табл. 15 ПУЭ РК из ссылки СП РК, п. 9.3 — токи кабелей)",
        DESIGN_DEFAULT,
    ),
    "MIN_GROUNDING_DIST_FROM_ENTRANCE_M": (
        "задание № 4 (нормы нет в СП РК, СО 153, РД 34.21.122-87 и ПУЭ РК: 3 м от входов в РД, п. 2.12 — для токоотводов)",
        DESIGN_DEFAULT,
    ),
    "ROLLING_SPHERE_RADIUS_BY_LEVEL_M": ("СП РК 2.04-103-2013, табл. 2 и п. 7.2", VERIFIED),
    "DEFAULT_LIGHTNING_PROTECTION_LEVEL": ("решение инженера (уровень I)", DESIGN_DEFAULT),
    "DEFAULT_SO153_RELIABILITY": ("СО 153-34.21.122-2003, п. 2.2 (диапазон 0,9–0,999; принят максимум)", DESIGN_DEFAULT),
    "ZONE_A_H0_COEFF": ("РД 34.21.122-87, Приложение 3, п. 1.1 (зона А, h ≤ 150 м)", VERIFIED),
    "ZONE_A_R0_BASE": ("РД 34.21.122-87, Приложение 3, п. 1.1 (зона А, h ≤ 150 м)", VERIFIED),
    "ZONE_A_R0_SLOPE": ("РД 34.21.122-87, Приложение 3, п. 1.1 (зона А, h ≤ 150 м)", VERIFIED),
    "ZONE_B_H0_COEFF": ("РД 34.21.122-87, Приложение 3, п. 1.1 (зона Б, h ≤ 150 м)", VERIFIED),
    "ZONE_B_R0_COEFF": ("РД 34.21.122-87, Приложение 3, п. 1.1 (зона Б, h ≤ 150 м)", VERIFIED),
    "DEFAULT_VENT_ABOVE_RIDGE_M": ("задание № 4", DESIGN_DEFAULT),
    "ARRESTER_HEIGHT_SEARCH_STEP_M": ("задание № 4", DESIGN_DEFAULT),
    "DEFAULT_WALL_THICKNESS_M": ("задание № 5", DESIGN_DEFAULT),
}


def constants_with_status(status: Status) -> list[str]:
    return sorted(name for name, (_, item_status) in CONSTANT_SOURCES.items() if item_status == status)
