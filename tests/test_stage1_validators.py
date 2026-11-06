import pytest
from pydantic import ValidationError

from explosions_core.norms.constants_rk343 import (
    MAX_MOBILE_PAYLOAD_RATIO,
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
    MAX_PRP_GUARDHOUSE_DIST_M,
    MAX_RACK_SHELF_HEIGHT_OTHER_M,
    MAX_RACK_SHELF_HEIGHT_UNSEALED_BC_M,
    MAX_STACK_HEIGHT_PALLET_M,
    MAX_STACK_HEIGHT_STANDARD_M,
    MAX_TIERS_OTHER,
    MAX_TIERS_UNSEALED_BC,
)
from explosions_core.domain import (
    CompatibilityGroup,
    ExplosiveItem,
    InternalLayoutConfig,
    MobileWarehouseConfig,
    NormativeViolation,
    PackagingType,
    StorageBuilding,
    StorageMethod,
    LocationType,
    UnloadingPlatformConfig,
    ValidationResult,
    WarehouseCategory,
    WarehouseDuration,
    WarehouseProjectInput,
)
from explosions_core.validators.compatibility import check_storage_compatibility, validate_compatibility
from explosions_core.validators.layout_and_perimeter import (
    validate_internal_layout,
    validate_mobile_warehouse,
    validate_perimeter,
    validate_prp,
    validate_project,
)


def make_item(
    name: str = "Аммонит",
    group: CompatibilityGroup = CompatibilityGroup.B,
    mass_kg: float = 100.0,
    si_count: int = 0,
    **flags: bool,
) -> ExplosiveItem:
    return ExplosiveItem(name=name, group=group, mass_kg=mass_kg, si_count=si_count, **flags)


def make_storage(
    items: list[ExplosiveItem] | None = None,
    duration: WarehouseDuration = WarehouseDuration.PERMANENT,
    layout: InternalLayoutConfig | None = None,
    name: str = "Хранилище-1",
) -> StorageBuilding:
    return StorageBuilding(
        name=name,
        category=WarehouseCategory.BASIS,
        duration=duration,
        location_type=LocationType.SURFACE,
        items=items or [],
        layout=layout,
    )


def make_layout(**overrides) -> InternalLayoutConfig:
    base = {"storage_method": StorageMethod.STACK, "packaging": PackagingType.BOX}
    base.update(overrides)
    return InternalLayoutConfig(**base)


def make_project(**overrides) -> WarehouseProjectInput:
    return WarehouseProjectInput(name="Карьер-1", **overrides)


def codes(result: ValidationResult) -> list[str]:
    return [violation.code for violation in result.violations]


COMPLIANT_PERIMETER = {
    "forbidden_zone_width_m": MIN_FORBIDDEN_ZONE_WIDTH_M,
    "fence_height_m": MIN_FENCE_HEIGHT_PERMANENT_M,
    "fence_to_nearest_storage_m": MIN_DIST_FENCE_TO_STORAGE_M,
    "fence_to_guardhouse_m": MIN_DIST_FENCE_TO_GUARDHOUSE_M,
    "fence_to_tare_storage_m": MIN_DIST_FENCE_TO_TARE_STORAGE_M,
    "open_fire_ban_radius_m": MIN_OPEN_FIRE_BAN_RADIUS_M,
}


# Модуль 1: совместимость

def test_single_compatibility_group_is_valid():
    storage = make_storage([make_item(group=CompatibilityGroup.B), make_item(group=CompatibilityGroup.B)])
    assert check_storage_compatibility(storage).is_valid


def test_empty_storage_is_valid():
    assert check_storage_compatibility(make_storage()).is_valid


def test_mixed_groups_in_one_storage_violate_clause_8():
    storage = make_storage(
        [
            make_item(name="Аммонит", group=CompatibilityGroup.B),
            make_item(name="Средство инициирования", group=CompatibilityGroup.S, is_initiating_device=True),
        ]
    )
    result = check_storage_compatibility(storage)
    assert codes(result) == ["COMPAT_MIXED_GROUPS"]
    assert "п. 8" in result.violations[0].clause
    assert result.violations[0].actual_value == "B, S"


def test_black_powder_group_d_with_smokeless_powder_group_c_is_allowed():
    storage = make_storage(
        [
            make_item(name="Дымный порох", group=CompatibilityGroup.D, is_black_powder=True),
            make_item(name="Бездымный порох", group=CompatibilityGroup.C, is_smokeless_powder=True),
        ]
    )
    assert check_storage_compatibility(storage).is_valid


def test_group_d_without_black_powder_flag_breaks_powder_exception():
    storage = make_storage(
        [
            make_item(name="Неизвестный состав", group=CompatibilityGroup.D),
            make_item(name="Бездымный порох", group=CompatibilityGroup.C, is_smokeless_powder=True),
        ]
    )
    assert codes(check_storage_compatibility(storage)) == ["COMPAT_MIXED_GROUPS"]


def test_group_c_without_smokeless_flag_breaks_powder_exception():
    storage = make_storage(
        [
            make_item(name="Дымный порох", group=CompatibilityGroup.D, is_black_powder=True),
            make_item(name="Неизвестный состав", group=CompatibilityGroup.C),
        ]
    )
    assert codes(check_storage_compatibility(storage)) == ["COMPAT_MIXED_GROUPS"]


def test_powder_exception_does_not_cover_third_group():
    storage = make_storage(
        [
            make_item(name="Дымный порох", group=CompatibilityGroup.D, is_black_powder=True),
            make_item(name="Бездымный порох", group=CompatibilityGroup.C, is_smokeless_powder=True),
            make_item(name="Аммонит", group=CompatibilityGroup.B),
        ]
    )
    assert codes(check_storage_compatibility(storage)) == ["COMPAT_MIXED_GROUPS"]


@pytest.mark.parametrize("other", [CompatibilityGroup.B, CompatibilityGroup.C, CompatibilityGroup.D])
def test_group_g_with_b_c_d_is_allowed_by_clause_9_2(other):
    storage = make_storage([make_item(name="Огнепроводный шнур", group=CompatibilityGroup.G), make_item(group=other)])
    assert check_storage_compatibility(storage).is_valid


def test_group_g_with_group_e_is_not_allowed():
    storage = make_storage([make_item(group=CompatibilityGroup.G), make_item(group=CompatibilityGroup.E)])
    assert codes(check_storage_compatibility(storage)) == ["COMPAT_MIXED_GROUPS"]


def test_detonating_cord_d_with_detonators_b_is_allowed_by_clause_9_3():
    storage = make_storage(
        [
            make_item(name="Детонирующий шнур", group=CompatibilityGroup.D, is_detonating_cord=True),
            make_item(name="Электродетонаторы", group=CompatibilityGroup.B, is_initiating_device=True),
        ]
    )
    assert check_storage_compatibility(storage).is_valid


def test_explosive_d_with_detonators_b_is_not_allowed():
    storage = make_storage(
        [
            make_item(name="Гранулит", group=CompatibilityGroup.D),
            make_item(name="Электродетонаторы", group=CompatibilityGroup.B, is_initiating_device=True),
        ]
    )
    result = check_storage_compatibility(storage)
    assert codes(result) == ["COMPAT_MIXED_GROUPS"]
    assert "B+D" in result.violations[0].description


def test_validate_compatibility_collects_violations_from_all_storages():
    bad_storage = make_storage([make_item(group=CompatibilityGroup.B), make_item(group=CompatibilityGroup.S)], name="A")
    good_storage = make_storage([make_item(group=CompatibilityGroup.B)], name="B")
    result = validate_compatibility([bad_storage, good_storage, bad_storage])
    assert codes(result) == ["COMPAT_MIXED_GROUPS", "COMPAT_MIXED_GROUPS"]


# Модуль 2: внутренняя планировка (п. 579-580)

def test_layout_is_skipped_when_not_provided():
    assert validate_internal_layout(make_storage()).is_valid


def test_wall_clearance_below_minimum_violates():
    result = validate_internal_layout(make_storage(layout=make_layout(wall_clearance_m=0.1)))
    assert codes(result) == ["LAYOUT_WALL_CLEARANCE"]
    assert result.violations[0].required_value == MIN_WALL_CLEARANCE_M


def test_wall_clearance_at_minimum_is_valid():
    assert validate_internal_layout(make_storage(layout=make_layout(wall_clearance_m=0.2))).is_valid


def test_floor_deck_below_minimum_violates():
    result = validate_internal_layout(make_storage(layout=make_layout(floor_deck_height_m=0.05)))
    assert codes(result) == ["LAYOUT_FLOOR_DECK_HEIGHT"]


def test_floor_deck_at_minimum_is_valid():
    assert validate_internal_layout(make_storage(layout=make_layout(floor_deck_height_m=MIN_FLOOR_DECK_HEIGHT_M))).is_valid


def test_stack_aisle_below_minimum_violates():
    result = validate_internal_layout(make_storage(layout=make_layout(aisle_width_stack_m=1.2)))
    assert codes(result) == ["LAYOUT_AISLE_WIDTH_STACK"]


def test_stack_aisle_at_minimum_is_valid():
    assert validate_internal_layout(make_storage(layout=make_layout(aisle_width_stack_m=MIN_AISLE_WIDTH_STACK_M))).is_valid


def test_rack_aisle_below_minimum_violates():
    result = validate_internal_layout(make_storage(layout=make_layout(aisle_width_rack_m=0.9)))
    assert codes(result) == ["LAYOUT_AISLE_WIDTH_RACK"]


def test_rack_aisle_at_minimum_is_valid():
    assert validate_internal_layout(make_storage(layout=make_layout(aisle_width_rack_m=MIN_AISLE_WIDTH_RACK_M))).is_valid


@pytest.mark.parametrize(
    ("packaging", "height"),
    [
        (PackagingType.BOX, MAX_STACK_HEIGHT_STANDARD_M + 0.1),
        (PackagingType.BAG, MAX_STACK_HEIGHT_STANDARD_M + 0.1),
        (PackagingType.PALLET, MAX_STACK_HEIGHT_PALLET_M + 0.1),
        (PackagingType.CONTAINER, MAX_STACK_HEIGHT_PALLET_M + 0.1),
    ],
)
def test_stack_height_above_limit_violates(packaging, height):
    result = validate_internal_layout(make_storage(layout=make_layout(packaging=packaging, stack_height_m=height)))
    assert codes(result) == ["LAYOUT_STACK_HEIGHT"]


def test_stack_height_2_1_m_on_bags_violates_standard_limit():
    result = validate_internal_layout(make_storage(layout=make_layout(packaging=PackagingType.BAG, stack_height_m=2.1)))
    assert codes(result) == ["LAYOUT_STACK_HEIGHT"]
    assert result.violations[0].required_value == MAX_STACK_HEIGHT_STANDARD_M


@pytest.mark.parametrize(
    ("packaging", "height"),
    [
        (PackagingType.BOX, MAX_STACK_HEIGHT_STANDARD_M),
        (PackagingType.PALLET, MAX_STACK_HEIGHT_PALLET_M),
        (PackagingType.CONTAINER, MAX_STACK_HEIGHT_PALLET_M),
    ],
)
def test_stack_height_at_limit_is_valid(packaging, height):
    assert validate_internal_layout(make_storage(layout=make_layout(packaging=packaging, stack_height_m=height))).is_valid


def test_pallet_stack_2_5_m_is_valid():
    assert validate_internal_layout(make_storage(layout=make_layout(packaging=PackagingType.PALLET, stack_height_m=2.5))).is_valid


def test_rack_shelf_for_unsealed_bc_above_1_7_violates():
    layout = make_layout(
        storage_method=StorageMethod.RACK,
        unsealed_bc_or_black_powder=True,
        rack_shelf_height_m=MAX_RACK_SHELF_HEIGHT_UNSEALED_BC_M + 0.1,
    )
    result = validate_internal_layout(make_storage(layout=layout))
    assert codes(result) == ["LAYOUT_RACK_SHELF_HEIGHT"]
    assert result.violations[0].required_value == MAX_RACK_SHELF_HEIGHT_UNSEALED_BC_M


def test_rack_shelf_for_unsealed_bc_at_limit_is_valid():
    layout = make_layout(
        storage_method=StorageMethod.RACK,
        unsealed_bc_or_black_powder=True,
        rack_shelf_height_m=MAX_RACK_SHELF_HEIGHT_UNSEALED_BC_M,
        tiers_per_shelf=MAX_TIERS_UNSEALED_BC,
    )
    assert validate_internal_layout(make_storage(layout=layout)).is_valid


def test_unsealed_bc_with_two_tiers_violates():
    layout = make_layout(
        storage_method=StorageMethod.RACK,
        unsealed_bc_or_black_powder=True,
        tiers_per_shelf=MAX_TIERS_UNSEALED_BC + 1,
    )
    assert codes(validate_internal_layout(make_storage(layout=layout))) == ["LAYOUT_RACK_TIERS"]


def test_other_rack_shelf_above_2_0_violates():
    layout = make_layout(
        storage_method=StorageMethod.RACK,
        rack_shelf_height_m=MAX_RACK_SHELF_HEIGHT_OTHER_M + 0.1,
    )
    assert codes(validate_internal_layout(make_storage(layout=layout))) == ["LAYOUT_RACK_SHELF_HEIGHT"]


def test_other_rack_with_two_tiers_is_valid_and_three_tiers_violates():
    valid = make_layout(storage_method=StorageMethod.RACK, tiers_per_shelf=MAX_TIERS_OTHER)
    invalid = make_layout(storage_method=StorageMethod.RACK, tiers_per_shelf=MAX_TIERS_OTHER + 1)
    assert validate_internal_layout(make_storage(layout=valid)).is_valid
    assert codes(validate_internal_layout(make_storage(layout=invalid))) == ["LAYOUT_RACK_TIERS"]


# Модуль 2: периметр и генплан

def test_compliant_perimeter_is_valid():
    assert validate_perimeter(make_project(**COMPLIANT_PERIMETER)).is_valid


def test_perimeter_skipped_when_values_not_provided():
    assert validate_perimeter(make_project()).is_valid


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("forbidden_zone_width_m", MIN_FORBIDDEN_ZONE_WIDTH_M - 0.1, "PERIMETER_FORBIDDEN_ZONE_WIDTH"),
        ("fence_height_m", MIN_FENCE_HEIGHT_PERMANENT_M - 0.1, "PERIMETER_FENCE_HEIGHT"),
        ("fence_to_nearest_storage_m", MIN_DIST_FENCE_TO_STORAGE_M - 0.1, "PERIMETER_FENCE_TO_STORAGE"),
        ("fence_to_guardhouse_m", MIN_DIST_FENCE_TO_GUARDHOUSE_M - 0.1, "PERIMETER_FENCE_TO_GUARDHOUSE"),
        ("fence_to_tare_storage_m", MIN_DIST_FENCE_TO_TARE_STORAGE_M - 0.1, "PERIMETER_FENCE_TO_TARE_STORAGE"),
        ("open_fire_ban_radius_m", MIN_OPEN_FIRE_BAN_RADIUS_M - 0.1, "PERIMETER_OPEN_FIRE_BAN_RADIUS"),
    ],
)
def test_perimeter_below_minimum_violates(field, value, code):
    values = {**COMPLIANT_PERIMETER, field: value}
    assert codes(validate_perimeter(make_project(**values))) == [code]


def test_permanent_fence_2_m_violates_clause_593():
    values = {**COMPLIANT_PERIMETER, "fence_height_m": 2.0}
    result = validate_perimeter(make_project(**values))
    assert codes(result) == ["PERIMETER_FENCE_HEIGHT"]
    assert "п. 593" in result.violations[0].clause


def test_temporary_warehouse_fence_2_m_is_valid_and_lower_violates_clause_618():
    storages = [make_storage(duration=WarehouseDuration.TEMPORARY)]
    valid = {**COMPLIANT_PERIMETER, "fence_height_m": MIN_FENCE_HEIGHT_TEMPORARY_M}
    assert validate_perimeter(make_project(storages=storages, **valid)).is_valid
    invalid = {**COMPLIANT_PERIMETER, "fence_height_m": MIN_FENCE_HEIGHT_TEMPORARY_M - 0.1}
    result = validate_perimeter(make_project(storages=storages, **invalid))
    assert codes(result) == ["PERIMETER_FENCE_HEIGHT"]
    assert "п. 618" in result.violations[0].clause


def test_short_term_warehouse_uses_clause_621_limits():
    storages = [make_storage(duration=WarehouseDuration.SHORT_TERM)]
    compliant = {
        "fence_height_m": MIN_FENCE_HEIGHT_SHORT_TERM_M,
        "fence_to_nearest_storage_m": MIN_DIST_FENCE_TO_STORAGE_SHORT_TERM_M,
        "fence_to_guardhouse_m": MIN_DIST_FENCE_TO_GUARDHOUSE_SHORT_TERM_M,
        "open_fire_ban_radius_m": MIN_OPEN_FIRE_BAN_RADIUS_M,
    }
    assert validate_perimeter(make_project(storages=storages, **compliant)).is_valid
    broken = {**compliant, "fence_height_m": 1.4, "fence_to_nearest_storage_m": 19.0, "fence_to_guardhouse_m": 14.0}
    result = validate_perimeter(make_project(storages=storages, **broken))
    assert codes(result) == ["PERIMETER_FENCE_HEIGHT", "PERIMETER_FENCE_TO_STORAGE", "PERIMETER_FENCE_TO_GUARDHOUSE"]
    assert all("п. 621" in violation.clause for violation in result.violations)


def test_permanent_requirements_govern_mixed_warehouse():
    storages = [make_storage(duration=WarehouseDuration.SHORT_TERM), make_storage(name="Постоянное")]
    values = {**COMPLIANT_PERIMETER, "fence_height_m": MIN_FENCE_HEIGHT_SHORT_TERM_M}
    assert codes(validate_perimeter(make_project(storages=storages, **values))) == ["PERIMETER_FENCE_HEIGHT"]


def test_guardhouse_inside_wider_forbidden_zone_violates_clause_592():
    values = {**COMPLIANT_PERIMETER, "forbidden_zone_width_m": 60.0, "fence_to_guardhouse_m": 55.0}
    result = validate_perimeter(make_project(**values))
    assert codes(result) == ["PERIMETER_FENCE_TO_GUARDHOUSE"]
    assert result.violations[0].required_value == 60.0


# Погрузочно-разгрузочная площадка (п. 48)

def test_prp_compliant_is_valid():
    platform = UnloadingPlatformConfig(
        fence_height_m=MIN_PRP_FENCE_HEIGHT_M,
        loading_point_to_fence_m=MIN_PRP_FENCE_DIST_M,
        switch_distance_m=MIN_PRP_SWITCH_DIST_M,
        guardhouse_distance_m=MAX_PRP_GUARDHOUSE_DIST_M,
    )
    assert validate_prp(make_project(unloading_platform=platform)).is_valid


def test_prp_loading_point_closer_than_15_m_to_fence_violates():
    platform = UnloadingPlatformConfig(loading_point_to_fence_m=14.0)
    result = validate_prp(make_project(unloading_platform=platform))
    assert codes(result) == ["PRP_FENCE_DISTANCE"]
    assert result.violations[0].actual_value == 14.0
    assert result.violations[0].required_value == MIN_PRP_FENCE_DIST_M


def test_prp_fence_lower_than_2_m_violates():
    platform = UnloadingPlatformConfig(fence_height_m=1.8)
    assert codes(validate_prp(make_project(unloading_platform=platform))) == ["PRP_FENCE_HEIGHT"]


def test_prp_switch_closer_than_50_m_violates():
    platform = UnloadingPlatformConfig(switch_distance_m=49.0)
    assert codes(validate_prp(make_project(unloading_platform=platform))) == ["PRP_SWITCH_DISTANCE"]


def test_prp_guardhouse_farther_than_50_m_violates():
    platform = UnloadingPlatformConfig(guardhouse_distance_m=51.0)
    assert codes(validate_prp(make_project(unloading_platform=platform))) == ["PRP_GUARDHOUSE_DISTANCE"]


def test_prp_skipped_without_platform():
    assert validate_prp(make_project()).is_valid


# Перевозка ВМ (п. 74); п. 62–66 исключены и не проверяются

def make_mobile(**overrides) -> MobileWarehouseConfig:
    base = {
        "vehicle_name": "Грузовик-1",
        "rated_payload_kg": 10000.0,
        "payload_kg": 6000.0,
        "powder_separation_m": MIN_MOBILE_POWDER_SEPARATION_M,
    }
    base.update(overrides)
    return MobileWarehouseConfig(**base)


def test_mobile_compliant_is_valid():
    assert validate_mobile_warehouse(make_project(mobile_warehouse=make_mobile())).is_valid


def test_mobile_payload_at_two_thirds_is_valid():
    payload = 10000.0 * MAX_MOBILE_PAYLOAD_RATIO
    assert validate_mobile_warehouse(make_project(mobile_warehouse=make_mobile(payload_kg=payload))).is_valid


def test_mobile_overload_above_two_thirds_violates():
    result = validate_mobile_warehouse(make_project(mobile_warehouse=make_mobile(payload_kg=7000.0)))
    assert codes(result) == ["MOBILE_PAYLOAD_OVERLOAD"]
    assert result.violations[0].actual_value == 7000.0


def test_mobile_powder_closer_than_0_5_m_to_other_vm_violates():
    items = [
        make_item(name="Порох", group=CompatibilityGroup.C, is_smokeless_powder=True),
        make_item(name="Перфораторный заряд", group=CompatibilityGroup.S),
    ]
    mobile = make_mobile(items=items, powder_separation_m=0.4)
    assert codes(validate_mobile_warehouse(make_project(mobile_warehouse=mobile))) == ["MOBILE_POWDER_SEPARATION"]


def test_mobile_powder_separation_is_not_checked_without_mixing():
    items = [make_item(name="Порох", group=CompatibilityGroup.C, is_smokeless_powder=True)]
    mobile = make_mobile(items=items, powder_separation_m=0.1)
    assert validate_mobile_warehouse(make_project(mobile_warehouse=mobile)).is_valid


def test_mobile_payload_rule_applies_only_to_joint_vv_and_si_transport():
    only_vv = [make_item(name="Гранулит", group=CompatibilityGroup.D)]
    mobile = make_mobile(items=only_vv, payload_kg=9000.0)
    assert validate_mobile_warehouse(make_project(mobile_warehouse=mobile)).is_valid
    joint = only_vv + [make_item(name="Детонаторы", group=CompatibilityGroup.B, is_initiating_device=True)]
    mobile = make_mobile(items=joint, payload_kg=9000.0)
    result = validate_mobile_warehouse(make_project(mobile_warehouse=mobile))
    assert codes(result) == ["MOBILE_PAYLOAD_OVERLOAD"]
    assert "п. 74" in result.violations[0].clause


def test_specialized_vehicle_full_load_allowed_without_groups_b_and_f():
    items = [
        make_item(name="Гранулит", group=CompatibilityGroup.D),
        make_item(name="НСИ", group=CompatibilityGroup.S, is_initiating_device=True),
    ]
    mobile = make_mobile(items=items, payload_kg=10000.0, is_specialized_vehicle=True)
    assert validate_mobile_warehouse(make_project(mobile_warehouse=mobile)).is_valid
    with_b = items + [make_item(name="Детонаторы", group=CompatibilityGroup.B, is_initiating_device=True)]
    mobile = make_mobile(items=with_b, payload_kg=10000.0, is_specialized_vehicle=True)
    assert codes(validate_mobile_warehouse(make_project(mobile_warehouse=mobile))) == ["MOBILE_PAYLOAD_OVERLOAD"]


def test_mobile_skipped_without_config():
    assert validate_mobile_warehouse(make_project()).is_valid


# Агрегатор и модели

def test_validate_project_aggregates_all_modules():
    bad_storage = make_storage(
        [make_item(group=CompatibilityGroup.B), make_item(group=CompatibilityGroup.S)],
        layout=make_layout(wall_clearance_m=0.1),
    )
    project = make_project(
        storages=[bad_storage],
        fence_to_nearest_storage_m=10.0,
        unloading_platform=UnloadingPlatformConfig(loading_point_to_fence_m=5.0),
    )
    found = set(codes(validate_project(project)))
    assert {
        "COMPAT_MIXED_GROUPS",
        "LAYOUT_WALL_CLEARANCE",
        "PERIMETER_FENCE_TO_STORAGE",
        "PRP_FENCE_DISTANCE",
    } <= found


def test_validate_project_is_valid_for_compliant_project():
    project = make_project(**COMPLIANT_PERIMETER)
    assert validate_project(project).is_valid


def test_validation_result_is_valid_property():
    assert ValidationResult().is_valid
    violation = NormativeViolation(code="X", clause="п. 1", description="d", actual_value=1.0, required_value=2.0)
    assert not ValidationResult(violations=[violation]).is_valid


def test_explosive_item_rejects_negative_mass():
    with pytest.raises(ValidationError):
        ExplosiveItem(name="Аммонит", group=CompatibilityGroup.B, mass_kg=-1.0)
