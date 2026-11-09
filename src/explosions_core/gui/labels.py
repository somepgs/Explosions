"""Русские подписи полей, значений перечислений и кодов для интерфейса (без Qt)."""

from pydantic import ValidationError

from explosions_core.domain import (
    BermSoilMaterial,
    ChargePlacementType,
    CompatibilityGroup,
    DetonationFormulaType,
    DetonationMaterialClass,
    LightningMethod,
    LightningProtectionLevel,
    LightningReliability,
    LightningZoneType,
    LocationType,
    PackagingType,
    StorageMethod,
    UVVMethod,
    WarehouseCategory,
    WarehouseDuration,
)

ENUM_LABELS: dict[type, dict[str, str]] = {
    WarehouseCategory: {
        "basis": "основной склад",
        "expendable": "расходный склад",
    },
    WarehouseDuration: {
        "permanent": "постоянный",
        "temporary": "временный",
        "short_term": "кратковременный",
        "mobile": "передвижной",
    },
    LocationType: {
        "surface": "наземный",
        "semi_buried": "полууглубленный",
        "buried": "углубленный",
        "underground": "подземный",
    },
    CompatibilityGroup: {
        "A": "A (ВВ, не допускаемые к хранению по группе)",
        "B": "B (ВВ и СИ, группа B)",
        "C": "C (бездымный порох)",
        "D": "D (дымный порох, ВВ группы D)",
        "E": "E (ВВ группы E)",
        "F": "F (ВВ группы F)",
        "G": "G (ВВ группы G)",
        "N": "N (ВВ группы N)",
        "S": "S (средства инициирования)",
    },
    PackagingType: {
        "box": "ящик",
        "bag": "мешок",
        "pallet": "поддон",
        "container": "стропконтейнер",
    },
    StorageMethod: {
        "rack": "стеллажное",
        "stack": "штабельное",
    },
    DetonationMaterialClass: {
        "an_based": "на основе аммиачной селитры",
        "nitroester_40_plus": "нитроэфиры от 40 %",
        "tnt": "тротил",
        "detonators": "детонаторы",
    },
    ChargePlacementType: {
        "open_surface": "открытый (наземный) заряд",
        "buried_own_height": "углубленный на свою высоту",
    },
    BermSoilMaterial: {
        "plastic_clay_loam": "пластичный грунт (глина, суглинок)",
        "sandy_free_flowing": "сыпучий грунт (песок, супесь)",
        "stone_or_gravel": "камень, щебень (запрещено)",
        "combustible_material": "горючие материалы (запрещено)",
    },
    LightningMethod: {
        "rolling_sphere_sp_rk": "катящаяся сфера (СП РК)",
        "single_rod_so_153": "одиночный молниеотвод (СО 153)",
        "zones_rd_34_21_122": "зоны А и Б (РД 34.21.122-87)",
    },
    LightningProtectionLevel: {
        "I": "I",
        "II": "II",
        "III": "III",
    },
    LightningReliability: {
        "0.9": "0,9",
        "0.99": "0,99",
        "0.999": "0,999",
    },
    LightningZoneType: {
        "zone_a": "Зона А",
        "zone_b": "Зона Б",
    },
    DetonationFormulaType: {
        "formula_19": "формула (19)",
        "table_5": "таблица 5",
        "max_conservative": "максимум (консервативно)",
    },
    UVVMethod: {
        "table_2_formulas": "таблица 2 (формулы 10 и 11)",
        "table_3": "таблица 3",
    },
}

FIELD_LABELS: dict[str, str] = {
    "name": "Наименование",
    "storage_id": "Идентификатор хранилища",
    "category": "Категория склада",
    "duration": "Срок эксплуатации",
    "location_type": "Расположение",
    "berm": "Обвалование",
    "is_bermed": "Обвалованное хранилище",
    "items": "Взрывчатые материалы",
    "layout": "Внутренняя планировка",
    "stack_width_b_m": "Ширина штабеля b, м",
    "x_m": "Координата X, м",
    "y_m": "Координата Y, м",
    "length_m": "Длина здания, м",
    "width_m": "Ширина здания, м",
    "group": "Группа совместимости",
    "mass_kg": "Масса нетто, кг",
    "si_count": "Количество СИ, шт.",
    "is_initiating_device": "Средство инициирования",
    "is_black_powder": "Дымный порох",
    "is_smokeless_powder": "Бездымный порох",
    "tnt_equivalent_coeff": "Коэффициент тротилового эквивалента",
    "hazard_subclass": "Подкласс опасности",
    "detonation_class": "Класс по таблице 4 Приложения 11",
    "is_detonating_cord": "Детонирующий шнур",
    "forbidden_zone_width_m": "Ширина запретной зоны, м",
    "fence_height_m": "Высота ограды склада, м",
    "fence_to_nearest_storage_m": "Ограда до ближайшего хранилища, м",
    "fence_to_guardhouse_m": "Ограда до караульного помещения, м",
    "fence_to_tare_storage_m": "Ограда до склада тары, м",
    "open_fire_ban_radius_m": "Зона запрета открытого огня, м",
    "unloading_platform": "Погрузочно-разгрузочная площадка (ПРП)",
    "loading_point_to_fence_m": "Место погрузки до ограды ПРП, м",
    "switch_distance_m": "Удаление рубильника освещения, м",
    "guardhouse_distance_m": "Удаление караульного помещения, м",
    "mobile_warehouse": "Передвижной склад",
    "vehicle_name": "Наименование транспортного средства",
    "rated_payload_kg": "Паспортная грузоподъемность, кг",
    "payload_kg": "Фактическая загрузка, кг",
    "is_specialized_vehicle": "Специализированный автомобиль",
    "powder_separation_m": "Расстояние между порохами и прочими ВМ, м",
    "external_targets": "Внешние охраняемые объекты",
    "object_id": "Идентификатор объекта",
    "allowed_damage_degree": "Допустимая степень повреждения (1–5)",
    "custom_kv_override": "Свой коэффициент K_в / k_в",
    "actual_distance_m": "Фактическое расстояние, м",
    "topography_reduction_coeff": "Коэффициент рельефа",
    "bearing_deg": "Направление от хранилища, градусы",
    "table3_object_category": "Категория объекта по таблице 3 (1–3)",
    "total_net_explosive_mass_kg": "Проектная масса ВМ нетто, кг",
    "compatibility_group": "Группа совместимости хранилища",
    "is_unsealed": "Вскрытая тара",
    "storage_method": "Способ хранения",
    "packaging_type": "Упаковка",
    "is_mechanized": "Механизированная укладка",
    "unit_spec": "Параметры единицы тары",
    "wall_racks_count": "Пристенных линий стеллажей",
    "island_rows_count": "Островных линий (рядов)",
    "cross_aisles_count": "Поперечных проходов",
    "shelf_thickness_m": "Толщина полки, м",
    "floor_deck_height_m": "Высота настила от пола, м",
    "wall_clearance_m": "Отступ от стен, м",
    "shelf_vertical_gap_m": "Зазор между полками, м",
    "preferred_units_along_single_line": "Желаемое число мест в линии",
    "eaves_height_m": "Высота карниза, м",
    "ridge_height_m": "Высота конька, м",
    "load_top_height_m": "Верх штабеля (стеллажа), м",
    "sizing": "Расчет габаритов",
    "lightning": "Молниезащита",
    "crest_elevation_above_load_m": "Превышение гребня над грузом, м",
    "crest_width_m": "Ширина гребня, м",
    "soil_material": "Грунт вала",
    "natural_slope_angle_deg": "Угол откоса, градусы",
    "wall_to_inner_toe_clearance_m": "Отступ подошвы от стены, м",
    "has_entrance_screen_berm": "Вал-экран перед въездом",
    "entrance_opening_width_m": "Ширина проезда, м",
    "screen_overlap_each_side_m": "Перекрытие проезда, м",
    "method": "Метод расчета",
    "protection_level": "Уровень защиты",
    "reliability": "Надежность защиты",
    "zone_type": "Зона защиты",
    "masts": "Молниеотводы",
    "vent_height_m": "Высота вентшахты, м",
    "mast_id": "Обозначение мачты",
    "height_h_m": "Высота мачты, м",
    "x_m_mast": "Координата X мачты, м",
    "unit_gap_m": "Зазор между местами, м",
    "net_weight_kg": "Масса нетто места, кг",
    "gross_weight_kg": "Масса брутто места, кг",
    "length_m_unit": "Длина места, м",
    "width_m_unit": "Ширина места, м",
    "height_m_unit": "Высота места, м",
    "settings": "Настройки расчета",
    "detonation_formula": "Формула передачи детонации",
    "uvv_placement": "Расположение заряда для УВВ",
    "uvv_method": "Метод расчета УВВ",
    "wall_thickness_m": "Толщина стены, м",
    "total_loaded_height_m": "Полная высота груза, м",
    "units_per_cross_section": "Мест в поперечном сечении",
    "project": "Проект",
    "schema_version": "Версия схемы",
    "storage_designs": "Проектные данные хранилищ",
    "storages": "Хранилища",
}

SEVERITY_LABELS: dict[str, str] = {"error": "ОШИБКА", "warning": "Предупреждение"}

MODULE_LABELS: dict[str, str] = {
    "sizing": "Габариты хранилища",
    "berm": "Обвалование",
    "lightning": "Молниезащита",
    "detonation": "Передача детонации",
    "uvv": "Ударная воздушная волна",
    "validation": "Нормативные проверки",
    "project": "Проект",
}


def enum_label(value: object) -> str:
    """Подпись значения перечисления; для прочих значений — строковое представление."""
    raw = getattr(value, "value", value)
    for enum_type, labels in ENUM_LABELS.items():
        if isinstance(value, enum_type):
            return labels.get(str(raw), str(raw))
    return str(raw)


def enum_choices(enum_type: type) -> list[tuple[str, str]]:
    """Пары (значение, подпись) для выпадающего списка перечисления в порядке объявления."""
    labels = ENUM_LABELS.get(enum_type, {})
    return [(member.value, labels.get(member.value, member.value)) for member in enum_type]


def field_label(name: str) -> str:
    return FIELD_LABELS.get(name, name)


ERROR_MESSAGES: dict[str, str] = {
    "missing": "обязательное поле не заполнено",
    "extra_forbidden": "неизвестное поле",
    "greater_than": "должно быть больше {gt}",
    "greater_than_equal": "должно быть не меньше {ge}",
    "less_than": "должно быть меньше {lt}",
    "less_than_equal": "должно быть не больше {le}",
    "float_parsing": "должно быть числом",
    "float_type": "должно быть числом",
    "int_parsing": "должно быть целым числом",
    "int_type": "должно быть целым числом",
    "bool_parsing": "должно быть «да» или «нет»",
    "bool_type": "должно быть «да» или «нет»",
    "string_type": "должно быть текстом",
    "enum": "выберите значение из списка",
    "literal_error": "допустимо только значение {expected}",
}

UNION_TAGS = frozenset({"float", "int", "str", "bool", "none", "dict", "list", "model", "is-instance"})


def format_validation_error(exc: ValidationError, header: str = "Данные не соответствуют схеме проекта") -> str:
    """Человекочитаемый список ошибок схемы: путь к полю по-русски и пояснение."""
    lines = [header]
    seen: set[str] = set()
    for error in exc.errors():
        line = f"• {_location_text(error['loc'])}: {_error_message(error)}"
        if line not in seen:
            seen.add(line)
            lines.append(line)
    return "\n".join(lines)


def _location_text(loc: tuple) -> str:
    parts: list[str] = []
    for part in loc:
        if isinstance(part, int):
            parts.append(f"элемент {part + 1}")
        elif str(part) in UNION_TAGS:
            continue
        else:
            parts.append(FIELD_LABELS.get(str(part), str(part)))
    return " → ".join(parts) or "проект"


def _error_message(error: dict) -> str:
    template = ERROR_MESSAGES.get(error["type"])
    if template is None:
        return str(error["msg"])
    try:
        return template.format(**error.get("ctx", {}))
    except (KeyError, IndexError, ValueError):
        return str(error["msg"])
