"""Единый конвейер расчета проекта склада ВМ: от файла проекта к результатам всех модулей.

Ошибка одного объекта или модуля фиксируется как `CalculationIssue` и не прерывает расчет остальных.
Структурные ошибки файла проекта (дублирующиеся идентификаторы хранилищ) вызывают `ValueError`.
"""

from explosions_core.calc.berm_calculator import calculate_berm_design
from explosions_core.calc.geometry import storage_key
from explosions_core.calc.lightning_protection import calculate_lightning_protection, lightning_required_violation
from explosions_core.calc.safe_distances import SafeDistanceEngine
from explosions_core.calc.storage_sizing import StorageSizingCalculator
from explosions_core.domain import (
    BermDesignInput,
    BermRecord,
    CalculationIssue,
    DetonationPairResult,
    ExternalProtectedObject,
    LightningRecord,
    NormativeViolation,
    ProjectCalculationResult,
    ProjectDefinition,
    StorageBuilding,
    StorageDesignInput,
    StorageSizingRecord,
    UVVDistanceResult,
    UVVMethod,
    ValidationResult,
    WarehouseProjectInput,
)
from explosions_core.validators.layout_and_perimeter import validate_project

MASS_TOLERANCE_KG = 1e-6
LENGTH_TOLERANCE_M = 1e-9
MODULE_ERRORS = (ValueError, NotImplementedError)


def calculate_project(definition: ProjectDefinition) -> ProjectCalculationResult:
    project = definition.project
    _check_unique_storage_keys(project)
    issues: list[CalculationIssue] = []
    designs = _index_designs(definition.storage_designs, project, issues)
    wall = definition.settings.wall_thickness_m

    resolved: list[StorageBuilding] = []
    sizing_records: list[StorageSizingRecord] = []
    berm_records: list[BermRecord] = []
    lightning_records: list[LightningRecord] = []
    lightning_violations: list[NormativeViolation] = []
    for storage in project.storages:
        key = storage_key(storage)
        design = designs.get(key)
        storage, sizing = _resolve_sizing(storage, design, wall, issues)
        resolved.append(storage)
        if sizing is not None:
            sizing_records.append(sizing)
        berm = _calculate_berm(storage, design, sizing, issues)
        if berm is not None:
            berm_records.append(berm)
        lightning = _calculate_lightning(storage, design, issues)
        if lightning is not None:
            lightning_records.append(lightning)
        lightning_violation = lightning_required_violation(
            storage, key, has_protection=design is not None and design.lightning is not None
        )
        if lightning_violation is not None:
            lightning_violations.append(lightning_violation)

    resolved_project = project.model_copy(update={"storages": resolved})
    engine = SafeDistanceEngine(
        formula=definition.settings.detonation_formula,
        uvv_method=definition.settings.uvv_method,
    )
    detonation_results = _calculate_detonation(resolved, engine, issues)
    uvv_results = _calculate_uvv(resolved, project.external_targets, definition, engine, issues)
    validation = validate_project(resolved_project)
    validation = ValidationResult(violations=[*validation.violations, *lightning_violations])

    return ProjectCalculationResult(
        project=resolved_project,
        validation=validation,
        sizing_records=sizing_records,
        berm_records=berm_records,
        lightning_records=lightning_records,
        detonation_results=detonation_results,
        uvv_results=uvv_results,
        issues=issues,
    )


def _check_unique_storage_keys(project: WarehouseProjectInput) -> None:
    keys = [storage_key(storage) for storage in project.storages]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        raise ValueError(f"Повторяются идентификаторы хранилищ: {', '.join(duplicates)}")


def _index_designs(
    designs: list[StorageDesignInput],
    project: WarehouseProjectInput,
    issues: list[CalculationIssue],
) -> dict[str, StorageDesignInput]:
    storage_keys = {storage_key(storage) for storage in project.storages}
    indexed: dict[str, StorageDesignInput] = {}
    for design in designs:
        if design.storage_id in indexed:
            raise ValueError(f"Повторяются проектные данные хранилища: {design.storage_id}")
        indexed[design.storage_id] = design
        if design.storage_id not in storage_keys:
            issues.append(
                CalculationIssue(
                    severity="error",
                    module="design",
                    object_id=design.storage_id,
                    message="Проектные данные указаны для хранилища, которого нет в проекте",
                )
            )
    return indexed


def _resolve_sizing(
    storage: StorageBuilding,
    design: StorageDesignInput | None,
    wall: float,
    issues: list[CalculationIssue],
) -> tuple[StorageBuilding, StorageSizingRecord | None]:
    key = storage_key(storage)
    if design is None or design.sizing is None:
        return storage, None
    try:
        result = StorageSizingCalculator().calculate(design.sizing)
    except MODULE_ERRORS as exc:
        issues.append(CalculationIssue(severity="error", module="sizing", object_id=key, message=str(exc)))
        return storage, None

    record = StorageSizingRecord(storage_id=key, sizing_input=design.sizing, result=result)
    required_length = result.min_internal_length_m + 2.0 * wall
    required_width = result.min_internal_width_m + 2.0 * wall
    updates: dict[str, float] = {}
    if storage.length_m is None:
        updates["length_m"] = required_length
    elif storage.length_m < required_length - LENGTH_TOLERANCE_M:
        issues.append(_building_too_small(key, "длина", storage.length_m, required_length))
    if storage.width_m is None:
        updates["width_m"] = required_width
    elif storage.width_m < required_width - LENGTH_TOLERANCE_M:
        issues.append(_building_too_small(key, "ширина", storage.width_m, required_width))

    if storage.items:
        items_mass = sum(item.mass_kg for item in storage.items)
        if abs(items_mass - design.sizing.total_net_explosive_mass_kg) > MASS_TOLERANCE_KG:
            issues.append(
                CalculationIssue(
                    severity="warning",
                    module="sizing",
                    object_id=key,
                    message=(
                        f"Масса по партиям ВМ ({items_mass:.2f} кг) не совпадает с массой для расчета "
                        f"стеллажей/штабелей ({design.sizing.total_net_explosive_mass_kg:.2f} кг)"
                    ),
                )
            )
    if updates:
        storage = storage.model_copy(update=updates)
    return storage, record


def _building_too_small(key: str, dimension: str, actual: float, required: float) -> CalculationIssue:
    return CalculationIssue(
        severity="warning",
        module="sizing",
        object_id=key,
        message=f"{dimension.capitalize()} здания {actual:.2f} м меньше требуемой {required:.2f} м (п. 579–580)",
    )


def _calculate_berm(
    storage: StorageBuilding,
    design: StorageDesignInput | None,
    sizing: StorageSizingRecord | None,
    issues: list[CalculationIssue],
) -> BermRecord | None:
    key = storage_key(storage)
    if design is None or design.berm is None:
        return None
    missing = _missing_building_fields(storage, design, need_eaves=False)
    load_top = design.load_top_height_m
    if load_top is None and sizing is not None:
        load_top = sizing.result.total_loaded_height_m
    if missing is None and load_top is None:
        missing = "Не задан верхний уровень штабеля (стеллажа): укажите load_top_height_m или раздел sizing (п. 604)"
    if missing:
        issues.append(CalculationIssue(severity="error", module="berm", object_id=key, message=missing))
        return None
    try:
        berm_input = BermDesignInput(
            **design.berm.model_dump(),
            storage_length_m=storage.length_m,
            storage_width_m=storage.width_m,
            load_top_height_m=load_top,
        )
        result = calculate_berm_design(berm_input)
    except MODULE_ERRORS as exc:
        issues.append(CalculationIssue(severity="error", module="berm", object_id=key, message=str(exc)))
        return None
    return BermRecord(storage_id=key, berm_input=berm_input, result=result)


def _calculate_lightning(
    storage: StorageBuilding,
    design: StorageDesignInput | None,
    issues: list[CalculationIssue],
) -> LightningRecord | None:
    key = storage_key(storage)
    if design is None or design.lightning is None:
        return None
    missing = _missing_building_fields(storage, design, need_eaves=True)
    if missing is None and design.ridge_height_m is None:
        missing = "Не задана высота конька кровли для расчета молниезащиты"
    if missing:
        issues.append(CalculationIssue(severity="error", module="lightning", object_id=key, message=missing))
        return None
    spec = design.lightning
    masts = list(spec.masts)
    try:
        result = calculate_lightning_protection(
            masts,
            spec.zone_type,
            storage.length_m,
            storage.width_m,
            design.eaves_height_m,
            design.ridge_height_m,
            vent_height_m=spec.vent_height_m,
            method=spec.method,
            protection_level=spec.protection_level,
            reliability=spec.reliability,
        )
    except MODULE_ERRORS as exc:
        issues.append(CalculationIssue(severity="error", module="lightning", object_id=key, message=str(exc)))
        return None
    return LightningRecord(
        storage_id=key,
        method=spec.method,
        protection_level=spec.protection_level,
        reliability=spec.reliability,
        zone_type=spec.zone_type,
        masts=masts,
        storage_length_m=storage.length_m,
        storage_width_m=storage.width_m,
        eaves_height_m=design.eaves_height_m,
        ridge_height_m=design.ridge_height_m,
        vent_height_m=spec.vent_height_m,
        result=result,
    )


def _missing_building_fields(storage: StorageBuilding, design: StorageDesignInput, *, need_eaves: bool) -> str | None:
    if storage.length_m is None or storage.width_m is None:
        return "Не заданы габариты здания: укажите длину и ширину или раздел sizing"
    if need_eaves and design.eaves_height_m is None:
        return "Не задана высота карниза здания"
    return None


def _calculate_detonation(
    storages: list[StorageBuilding],
    engine: SafeDistanceEngine,
    issues: list[CalculationIssue],
) -> list[DetonationPairResult]:
    placed = [storage for storage in storages if _has_plan_geometry(storage)]
    placed_ids = {id(storage) for storage in placed}
    if len(storages) > 1:
        for storage in storages:
            if id(storage) not in placed_ids:
                issues.append(
                    CalculationIssue(
                        severity="warning",
                        module="detonation",
                        object_id=storage_key(storage),
                        message="Нет координат или габаритов, хранилище не учтено в расчете r_д",
                    )
                )
    results: list[DetonationPairResult] = []
    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            pair_id = f"{storage_key(placed[i])}-{storage_key(placed[j])}"
            try:
                results.append(engine.detonation_pair(placed[i], placed[j]))
            except MODULE_ERRORS as exc:
                issues.append(CalculationIssue(severity="error", module="detonation", object_id=pair_id, message=str(exc)))
    return results


def _has_plan_geometry(storage: StorageBuilding) -> bool:
    return (
        storage.x_m is not None
        and storage.y_m is not None
        and storage.length_m is not None
        and storage.width_m is not None
    )


def _calculate_uvv(
    storages: list[StorageBuilding],
    targets: list[ExternalProtectedObject],
    definition: ProjectDefinition,
    engine: SafeDistanceEngine,
    issues: list[CalculationIssue],
) -> list[UVVDistanceResult]:
    results: list[UVVDistanceResult] = []
    governing_mass = None
    if definition.settings.uvv_method == UVVMethod.TABLE_3:
        governing_mass = engine.table3_governing_mass(storages)
    for storage in storages:
        for target in targets:
            object_id = f"{storage_key(storage)}-{target.object_id}"
            try:
                results.append(
                    engine.uvv(
                        storage, target, definition.settings.uvv_placement, explosive_mass_kg=governing_mass
                    )
                )
            except MODULE_ERRORS as exc:
                issues.append(CalculationIssue(severity="error", module="uvv", object_id=object_id, message=str(exc)))
    return results
