"""Модуль 2 и часть Модуля 4: внутренняя планировка, периметр, ПРП, кратковременные и передвижные склады."""

from explosions_core.domain import (
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
    MAX_SHORT_TERM_SINGLE_STORAGE_SI_PCS,
    MAX_SHORT_TERM_SINGLE_STORAGE_VM_KG,
    MAX_SHORT_TERM_TOTAL_SI_PCS,
    MAX_SHORT_TERM_TOTAL_VM_KG,
    MAX_STACK_HEIGHT_PALLET_M,
    MAX_STACK_HEIGHT_STANDARD_M,
    MAX_TIERS_OTHER,
    MAX_TIERS_UNSEALED_BC,
    MIN_AISLE_WIDTH_RACK_M,
    MIN_AISLE_WIDTH_STACK_M,
    MIN_DIST_FENCE_TO_GUARDHOUSE_M,
    MIN_DIST_FENCE_TO_STORAGE_M,
    MIN_DIST_FENCE_TO_TARE_STORAGE_M,
    MIN_FENCE_HEIGHT_M,
    MIN_FLOOR_DECK_HEIGHT_M,
    MIN_FORBIDDEN_ZONE_WIDTH_M,
    MIN_MOBILE_POWDER_SEPARATION_M,
    MIN_MOBILE_SAFE_STANDOFF_M,
    MIN_OPEN_FIRE_BAN_RADIUS_M,
    MIN_PRP_FENCE_DIST_M,
    MIN_PRP_SWITCH_DIST_M,
    MIN_WALL_CLEARANCE_M,
)
from explosions_core.norms.references import (
    CLAUSE_MOBILE_PAYLOAD,
    CLAUSE_MOBILE_STANDOFF,
    CLAUSE_OPEN_FIRE,
    CLAUSE_PERIMETER,
    CLAUSE_PRP,
    CLAUSE_RACK,
    CLAUSE_SHORT_TERM,
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


def validate_perimeter(project: WarehouseProjectInput) -> ValidationResult:
    violations: list[NormativeViolation] = []
    _check_min(
        violations,
        code="PERIMETER_FORBIDDEN_ZONE_WIDTH",
        clause=CLAUSE_PERIMETER,
        title="Ширина запретной зоны от ограды склада",
        actual=project.forbidden_zone_width_m,
        minimum=MIN_FORBIDDEN_ZONE_WIDTH_M,
    )
    _check_min(
        violations,
        code="PERIMETER_FENCE_HEIGHT",
        clause=CLAUSE_PERIMETER,
        title="Высота ограждения склада и колючей проволоки",
        actual=project.fence_height_m,
        minimum=MIN_FENCE_HEIGHT_M,
    )
    _check_min(
        violations,
        code="PERIMETER_FENCE_TO_STORAGE",
        clause=CLAUSE_PERIMETER,
        title="Расстояние от ограды до ближайшего хранилища ВМ",
        actual=project.fence_to_nearest_storage_m,
        minimum=MIN_DIST_FENCE_TO_STORAGE_M,
    )
    _check_min(
        violations,
        code="PERIMETER_FENCE_TO_GUARDHOUSE",
        clause=CLAUSE_PERIMETER,
        title="Расстояние от ограды до караульного помещения",
        actual=project.fence_to_guardhouse_m,
        minimum=MIN_DIST_FENCE_TO_GUARDHOUSE_M,
    )
    _check_min(
        violations,
        code="PERIMETER_FENCE_TO_TARE_STORAGE",
        clause=CLAUSE_PERIMETER,
        title="Расстояние от ограды до склада тары",
        actual=project.fence_to_tare_storage_m,
        minimum=MIN_DIST_FENCE_TO_TARE_STORAGE_M,
    )
    _check_min(
        violations,
        code="PERIMETER_OPEN_FIRE_BAN_RADIUS",
        clause=CLAUSE_OPEN_FIRE,
        title="Радиус зоны запрета открытого огня и курения вокруг ВМ",
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


def validate_short_term_limits(project: WarehouseProjectInput) -> ValidationResult:
    violations: list[NormativeViolation] = []
    total_mass_kg = 0.0
    total_si_pcs = 0
    for storage in project.storages:
        if storage.duration != WarehouseDuration.SHORT_TERM:
            continue
        mass_kg = sum((item.mass_kg for item in storage.items if not item.is_initiating_device), 0.0)
        si_pcs = sum(item.si_count for item in storage.items)
        total_mass_kg += mass_kg
        total_si_pcs += si_pcs
        _check_max(
            violations,
            code="SHORT_TERM_SINGLE_STORAGE_VM",
            clause=CLAUSE_SHORT_TERM,
            title=f"Хранилище '{storage.name}': масса ВМ в одном хранилище",
            actual=mass_kg,
            maximum=MAX_SHORT_TERM_SINGLE_STORAGE_VM_KG,
            unit="кг",
        )
        _check_max(
            violations,
            code="SHORT_TERM_SINGLE_STORAGE_SI",
            clause=CLAUSE_SHORT_TERM,
            title=f"Хранилище '{storage.name}': количество СИ в одном хранилище",
            actual=si_pcs,
            maximum=MAX_SHORT_TERM_SINGLE_STORAGE_SI_PCS,
            unit="шт.",
        )
    _check_max(
        violations,
        code="SHORT_TERM_TOTAL_VM",
        clause=CLAUSE_SHORT_TERM,
        title="Суммарная масса ВМ кратковременного расходного склада",
        actual=total_mass_kg,
        maximum=MAX_SHORT_TERM_TOTAL_VM_KG,
        unit="кг",
    )
    _check_max(
        violations,
        code="SHORT_TERM_TOTAL_SI",
        clause=CLAUSE_SHORT_TERM,
        title="Суммарное количество СИ кратковременного расходного склада",
        actual=total_si_pcs,
        maximum=MAX_SHORT_TERM_TOTAL_SI_PCS,
        unit="шт.",
    )
    return ValidationResult(violations=violations)


def _is_powder(item: ExplosiveItem) -> bool:
    return item.is_black_powder or item.is_smokeless_powder


def validate_mobile_warehouse(project: WarehouseProjectInput) -> ValidationResult:
    mobile = project.mobile_warehouse
    if mobile is None:
        return ValidationResult()
    violations: list[NormativeViolation] = []
    _check_max(
        violations,
        code="MOBILE_PAYLOAD_OVERLOAD",
        clause=CLAUSE_MOBILE_PAYLOAD,
        title=f"Передвижной склад '{mobile.vehicle_name}': загрузка ТС",
        actual=mobile.payload_kg,
        maximum=mobile.rated_payload_kg * MAX_MOBILE_PAYLOAD_RATIO,
        unit="кг",
    )
    has_powder = any(_is_powder(item) for item in mobile.items)
    has_other = any(not _is_powder(item) for item in mobile.items)
    if has_powder and has_other:
        _check_min(
            violations,
            code="MOBILE_POWDER_SEPARATION",
            clause=CLAUSE_MOBILE_PAYLOAD,
            title=f"Передвижной склад '{mobile.vehicle_name}': расстояние между порохами/перфораторными зарядами и прочими ВМ",
            actual=mobile.powder_separation_m,
            minimum=MIN_MOBILE_POWDER_SEPARATION_M,
        )
    _check_min(
        violations,
        code="MOBILE_BLASTING_STANDOFF",
        clause=CLAUSE_MOBILE_STANDOFF,
        title=f"Передвижной склад '{mobile.vehicle_name}': удаление от места взрывных работ",
        actual=mobile.distance_to_blasting_site_m,
        minimum=MIN_MOBILE_SAFE_STANDOFF_M,
    )
    _check_min(
        violations,
        code="MOBILE_SETTLEMENT_STANDOFF",
        clause=CLAUSE_MOBILE_STANDOFF,
        title=f"Передвижной склад '{mobile.vehicle_name}': удаление от населенных пунктов",
        actual=mobile.distance_to_settlement_m,
        minimum=MIN_MOBILE_SAFE_STANDOFF_M,
    )
    return ValidationResult(violations=violations)


def validate_project(project: WarehouseProjectInput) -> ValidationResult:
    results: list[ValidationResult] = [validate_compatibility(project.storages)]
    results.extend(validate_internal_layout(storage) for storage in project.storages)
    results.append(validate_perimeter(project))
    results.append(validate_prp(project))
    results.append(validate_short_term_limits(project))
    results.append(validate_mobile_warehouse(project))
    violations = [violation for result in results for violation in result.violations]
    return ValidationResult(violations=violations)
