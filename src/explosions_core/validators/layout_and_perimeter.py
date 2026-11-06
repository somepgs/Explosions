"""Модуль 2 и часть Модуля 4: внутренняя планировка (п. 579–580), генплан склада (п. 16, 590, 592, 593, 618, 621),
ПРП (п. 48) и совместная перевозка ВВ и СИ (п. 74).

Пункты 62–66 (кратковременные расходные и передвижные склады) в редакции от 02.10.2025 исключены и не проверяются.
"""

from explosions_core.domain import (
    CompatibilityGroup,
    ExplosiveItem,
    NormativeViolation,
    PackagingType,
    StorageBuilding,
    StorageMethod,
    ValidationResult,
    WarehouseDuration,
    WarehouseProjectInput,
)
from explosions_core.norms.constants_rk343 import (
    MAX_MOBILE_PAYLOAD_RATIO,
    MAX_PRP_GUARDHOUSE_DIST_M,
    MAX_RACK_SHELF_HEIGHT_OTHER_M,
    MAX_RACK_SHELF_HEIGHT_UNSEALED_BC_M,
    MAX_STACK_HEIGHT_PALLET_M,
    MAX_STACK_HEIGHT_STANDARD_M,
    MAX_TIERS_OTHER,
    MAX_TIERS_UNSEALED_BC,
    MIN_AISLE_WIDTH_RACK_M,
    MIN_AISLE_WIDTH_STACK_M,
    MIN_DIST_FENCE_TO_GUARDHOUSE_M,
    MIN_DIST_FENCE_TO_GUARDHOUSE_SHORT_TERM_M,
    MIN_DIST_FENCE_TO_STORAGE_M,
    MIN_DIST_FENCE_TO_STORAGE_SHORT_TERM_M,
    MIN_DIST_FENCE_TO_TARE_STORAGE_M,
    MIN_FENCE_HEIGHT_PERMANENT_M,
    MIN_FENCE_HEIGHT_SHORT_TERM_M,
    MIN_FENCE_HEIGHT_TEMPORARY_M,
    MIN_FLOOR_DECK_HEIGHT_M,
    MIN_FORBIDDEN_ZONE_WIDTH_M,
    MIN_MOBILE_POWDER_SEPARATION_M,
    MIN_OPEN_FIRE_BAN_RADIUS_M,
    MIN_PRP_FENCE_DIST_M,
    MIN_PRP_FENCE_HEIGHT_M,
    MIN_PRP_SWITCH_DIST_M,
    MIN_WALL_CLEARANCE_M,
)
from explosions_core.norms.references import (
    CLAUSE_FENCE_PERMANENT,
    CLAUSE_FORBIDDEN_ZONE,
    CLAUSE_GUARDHOUSE,
    CLAUSE_MOBILE_PAYLOAD,
    CLAUSE_MOBILE_POWDER,
    CLAUSE_OPEN_FIRE,
    CLAUSE_PRP,
    CLAUSE_RACK,
    CLAUSE_SHORT_TERM,
    CLAUSE_TARE,
    CLAUSE_TEMPORARY_AS_PERMANENT,
    CLAUSE_TEMPORARY_FENCE,
)
from explosions_core.norms.references import CLAUSE_STACK as CLAUSE_LAYOUT
from explosions_core.validators.compatibility import validate_compatibility


def _check_min(
    violations: list[NormativeViolation],
    *,
    code: str,
    clause: str,
    title: str,
    actual: float | None,
    minimum: float,
    unit: str = "м",
) -> None:
    if actual is not None and actual < minimum:
        violations.append(
            NormativeViolation(
                code=code,
                clause=clause,
                description=f"{title}: фактически {actual} {unit}, требуется не менее {minimum} {unit}",
                actual_value=actual,
                required_value=minimum,
            )
        )


def _check_max(
    violations: list[NormativeViolation],
    *,
    code: str,
    clause: str,
    title: str,
    actual: float | None,
    maximum: float,
    unit: str = "м",
) -> None:
    if actual is not None and actual > maximum:
        violations.append(
            NormativeViolation(
                code=code,
                clause=clause,
                description=f"{title}: фактически {actual} {unit}, допускается не более {maximum} {unit}",
                actual_value=actual,
                required_value=maximum,
            )
        )


def validate_internal_layout(storage: StorageBuilding) -> ValidationResult:
    layout = storage.layout
    if layout is None:
        return ValidationResult()
    violations: list[NormativeViolation] = []
    prefix = f"Хранилище '{storage.name}'"
    _check_min(
        violations,
        code="LAYOUT_WALL_CLEARANCE",
        clause=CLAUSE_LAYOUT,
        title=f"{prefix}: отступ стеллажей и штабелей от стены",
        actual=layout.wall_clearance_m,
        minimum=MIN_WALL_CLEARANCE_M,
    )
    _check_min(
        violations,
        code="LAYOUT_FLOOR_DECK_HEIGHT",
        clause=CLAUSE_LAYOUT,
        title=f"{prefix}: высота настила от уровня пола",
        actual=layout.floor_deck_height_m,
        minimum=MIN_FLOOR_DECK_HEIGHT_M,
    )
    _check_min(
        violations,
        code="LAYOUT_AISLE_WIDTH_STACK",
        clause=CLAUSE_LAYOUT,
        title=f"{prefix}: ширина прохода между штабелями",
        actual=layout.aisle_width_stack_m,
        minimum=MIN_AISLE_WIDTH_STACK_M,
    )
    _check_min(
        violations,
        code="LAYOUT_AISLE_WIDTH_RACK",
        clause=CLAUSE_LAYOUT,
        title=f"{prefix}: ширина прохода между стеллажами",
        actual=layout.aisle_width_rack_m,
        minimum=MIN_AISLE_WIDTH_RACK_M,
    )
    if layout.stack_height_m is not None:
        if layout.packaging in (PackagingType.PALLET, PackagingType.CONTAINER):
            max_stack_height = MAX_STACK_HEIGHT_PALLET_M
        else:
            max_stack_height = MAX_STACK_HEIGHT_STANDARD_M
        _check_max(
            violations,
            code="LAYOUT_STACK_HEIGHT",
            clause=CLAUSE_LAYOUT,
            title=f"{prefix}: высота штабеля",
            actual=layout.stack_height_m,
            maximum=max_stack_height,
        )
    if layout.storage_method == StorageMethod.RACK:
        if layout.unsealed_bc_or_black_powder:
            max_shelf_height = MAX_RACK_SHELF_HEIGHT_UNSEALED_BC_M
            max_tiers = MAX_TIERS_UNSEALED_BC
        else:
            max_shelf_height = MAX_RACK_SHELF_HEIGHT_OTHER_M
            max_tiers = MAX_TIERS_OTHER
        _check_max(
            violations,
            code="LAYOUT_RACK_SHELF_HEIGHT",
            clause=CLAUSE_RACK,
            title=f"{prefix}: высота верхней полки стеллажа",
            actual=layout.rack_shelf_height_m,
            maximum=max_shelf_height,
        )
        _check_max(
            violations,
            code="LAYOUT_RACK_TIERS",
            clause=CLAUSE_RACK,
            title=f"{prefix}: количество мест по высоте на полке",
            actual=layout.tiers_per_shelf,
            maximum=max_tiers,
            unit="ряд(а)",
        )
    return ValidationResult(violations=violations)


_DURATION_PRIORITY = (WarehouseDuration.PERMANENT, WarehouseDuration.TEMPORARY, WarehouseDuration.SHORT_TERM)


def governing_warehouse_duration(project: WarehouseProjectInput) -> WarehouseDuration:
    """Тип склада для проверки генплана: наиболее строгий из сроков эксплуатации хранилищ (по умолчанию — постоянный)."""
    durations = {storage.duration for storage in project.storages}
    for duration in _DURATION_PRIORITY:
        if duration in durations:
            return duration
    return WarehouseDuration.PERMANENT


def validate_perimeter(project: WarehouseProjectInput) -> ValidationResult:
    """Генплан склада по типу: постоянный (п. 590, 592, 593), временный (п. 618), кратковременный (п. 621); огонь — п. 16."""
    violations: list[NormativeViolation] = []
    duration = governing_warehouse_duration(project)
    if duration == WarehouseDuration.SHORT_TERM:
        _check_min(
            violations,
            code="PERIMETER_FENCE_HEIGHT",
            clause=CLAUSE_SHORT_TERM,
            title="Высота ограды кратковременного склада",
            actual=project.fence_height_m,
            minimum=MIN_FENCE_HEIGHT_SHORT_TERM_M,
        )
        _check_min(
            violations,
            code="PERIMETER_FENCE_TO_STORAGE",
            clause=CLAUSE_SHORT_TERM,
            title="Расстояние от ограды до ближайшей стены хранилища",
            actual=project.fence_to_nearest_storage_m,
            minimum=MIN_DIST_FENCE_TO_STORAGE_SHORT_TERM_M,
        )
        _check_min(
            violations,
            code="PERIMETER_FENCE_TO_GUARDHOUSE",
            clause=CLAUSE_SHORT_TERM,
            title="Расстояние от ограды до караульного помещения",
            actual=project.fence_to_guardhouse_m,
            minimum=MIN_DIST_FENCE_TO_GUARDHOUSE_SHORT_TERM_M,
        )
    else:
        is_temporary = duration == WarehouseDuration.TEMPORARY
        general_clause = (lambda clause: CLAUSE_TEMPORARY_AS_PERMANENT if is_temporary else clause)
        _check_min(
            violations,
            code="PERIMETER_FORBIDDEN_ZONE_WIDTH",
            clause=general_clause(CLAUSE_FORBIDDEN_ZONE),
            title="Ширина запретной зоны от ограды склада",
            actual=project.forbidden_zone_width_m,
            minimum=MIN_FORBIDDEN_ZONE_WIDTH_M,
        )
        _check_min(
            violations,
            code="PERIMETER_FENCE_HEIGHT",
            clause=CLAUSE_TEMPORARY_FENCE if is_temporary else CLAUSE_FENCE_PERMANENT,
            title="Высота ограды склада",
            actual=project.fence_height_m,
            minimum=MIN_FENCE_HEIGHT_TEMPORARY_M if is_temporary else MIN_FENCE_HEIGHT_PERMANENT_M,
        )
        _check_min(
            violations,
            code="PERIMETER_FENCE_TO_STORAGE",
            clause=general_clause(CLAUSE_FENCE_PERMANENT),
            title="Расстояние от ограды до ближайшего хранилища",
            actual=project.fence_to_nearest_storage_m,
            minimum=MIN_DIST_FENCE_TO_STORAGE_M,
        )
        zone_width = max(MIN_FORBIDDEN_ZONE_WIDTH_M, project.forbidden_zone_width_m or 0.0)
        _check_min(
            violations,
            code="PERIMETER_FENCE_TO_GUARDHOUSE",
            clause=general_clause(CLAUSE_GUARDHOUSE),
            title="Караульное помещение размещается за запретной зоной: расстояние от ограды",
            actual=project.fence_to_guardhouse_m,
            minimum=max(MIN_DIST_FENCE_TO_GUARDHOUSE_M, zone_width),
        )
        _check_min(
            violations,
            code="PERIMETER_FENCE_TO_TARE_STORAGE",
            clause=general_clause(CLAUSE_TARE),
            title="Расстояние от ограды до сарая (навеса) для тары",
            actual=project.fence_to_tare_storage_m,
            minimum=MIN_DIST_FENCE_TO_TARE_STORAGE_M,
        )
    _check_min(
        violations,
        code="PERIMETER_OPEN_FIRE_BAN_RADIUS",
        clause=CLAUSE_OPEN_FIRE,
        title="Расстояние от места нахождения ВМ, ближе которого запрещены открытый огонь и курение",
        actual=project.open_fire_ban_radius_m,
        minimum=MIN_OPEN_FIRE_BAN_RADIUS_M,
    )
    return ValidationResult(violations=violations)


def validate_prp(project: WarehouseProjectInput) -> ValidationResult:
    platform = project.unloading_platform
    if platform is None:
        return ValidationResult()
    violations: list[NormativeViolation] = []
    _check_min(
        violations,
        code="PRP_FENCE_HEIGHT",
        clause=CLAUSE_PRP,
        title="Высота ограды ПРП",
        actual=platform.fence_height_m,
        minimum=MIN_PRP_FENCE_HEIGHT_M,
    )
    _check_min(
        violations,
        code="PRP_FENCE_DISTANCE",
        clause=CLAUSE_PRP,
        title="Расстояние от места погрузки/выгрузки до ограды ПРП",
        actual=platform.loading_point_to_fence_m,
        minimum=MIN_PRP_FENCE_DIST_M,
    )
    _check_min(
        violations,
        code="PRP_SWITCH_DISTANCE",
        clause=CLAUSE_PRP,
        title="Удаление рубильников освещения от ПРП",
        actual=platform.switch_distance_m,
        minimum=MIN_PRP_SWITCH_DIST_M,
    )
    _check_max(
        violations,
        code="PRP_GUARDHOUSE_DISTANCE",
        clause=CLAUSE_PRP,
        title="Удаление караульного помещения с телефоном от ПРП",
        actual=platform.guardhouse_distance_m,
        maximum=MAX_PRP_GUARDHOUSE_DIST_M,
    )
    return ValidationResult(violations=violations)


def _is_powder(item: ExplosiveItem) -> bool:
    return item.is_black_powder or item.is_smokeless_powder


def validate_mobile_warehouse(project: WarehouseProjectInput) -> ValidationResult:
    mobile = project.mobile_warehouse
    if mobile is None:
        return ValidationResult()
    violations: list[NormativeViolation] = []
    has_si = any(item.is_initiating_device for item in mobile.items)
    has_vv = any(not item.is_initiating_device for item in mobile.items)
    joint_transport = (has_si and has_vv) or not mobile.items
    has_b_or_f = any(item.group in (CompatibilityGroup.B, CompatibilityGroup.F) for item in mobile.items)
    full_load_allowed = mobile.is_specialized_vehicle and bool(mobile.items) and not has_b_or_f
    if joint_transport and not full_load_allowed:
        _check_payload(violations, mobile.vehicle_name, mobile.payload_kg, mobile.rated_payload_kg)
    has_powder = any(_is_powder(item) for item in mobile.items)
    has_other = any(not _is_powder(item) for item in mobile.items)
    if has_powder and has_other:
        _check_min(
            violations,
            code="MOBILE_POWDER_SEPARATION",
            clause=CLAUSE_MOBILE_POWDER,
            title=f"ТС '{mobile.vehicle_name}': расстояние между порохами/перфораторными зарядами и прочими ВМ",
            actual=mobile.powder_separation_m,
            minimum=MIN_MOBILE_POWDER_SEPARATION_M,
        )
    return ValidationResult(violations=violations)


def _check_payload(violations: list[NormativeViolation], vehicle: str, payload_kg: float, rated_kg: float) -> None:
    """п. 74, подпункт 1: при совместной перевозке ВВ и СИ загрузка не более 2/3 грузоподъемности.

    Если состав груза не задан, проверка выполняется в запас надежности. На специализированных автомобилях
    совместная доставка ВМ, кроме групп B и F, допускается до полной грузоподъемности (п. 74, последний абзац).
    """
    _check_max(
        violations,
        code="MOBILE_PAYLOAD_OVERLOAD",
        clause=CLAUSE_MOBILE_PAYLOAD,
        title=f"ТС '{vehicle}': загрузка при совместной перевозке ВВ и СИ",
        actual=payload_kg,
        maximum=rated_kg * MAX_MOBILE_PAYLOAD_RATIO,
        unit="кг",
    )


def validate_project(project: WarehouseProjectInput) -> ValidationResult:
    results: list[ValidationResult] = [validate_compatibility(project.storages)]
    results.extend(validate_internal_layout(storage) for storage in project.storages)
    results.append(validate_perimeter(project))
    results.append(validate_prp(project))
    results.append(validate_mobile_warehouse(project))
    violations = [violation for result in results for violation in result.violations]
    return ValidationResult(violations=violations)
