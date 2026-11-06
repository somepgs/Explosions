"""Модуль 1: проверка совместимости ВМ при хранении в одном хранилище."""

from explosions_core.domain import (
    CompatibilityGroup,
    ExplosiveItem,
    NormativeViolation,
    StorageBuilding,
    ValidationResult,
)
from explosions_core.norms.references import CLAUSE_COMPATIBILITY


def _is_allowed_powder_combination(items: list[ExplosiveItem]) -> bool:
    """Исключение п. 9: совместно допускаются дымные пороха группы D и бездымные пороха группы C."""
    groups = {item.group for item in items}
    if groups != {CompatibilityGroup.D, CompatibilityGroup.C}:
        return False
    group_d_items = [item for item in items if item.group == CompatibilityGroup.D]
    group_c_items = [item for item in items if item.group == CompatibilityGroup.C]
    return all(item.is_black_powder for item in group_d_items) and all(
        item.is_smokeless_powder for item in group_c_items
    )


def check_storage_compatibility(storage: StorageBuilding) -> ValidationResult:
    groups = {item.group for item in storage.items}
    if len(groups) <= 1:
        return ValidationResult()
    if _is_allowed_powder_combination(storage.items):
        return ValidationResult()
    groups_text = ", ".join(sorted(group.value for group in groups))
    return ValidationResult(
        violations=[
            NormativeViolation(
                code="COMPAT_MIXED_GROUPS",
                clause=CLAUSE_COMPATIBILITY,
                description=(
                    f"Хранилище '{storage.name}': раздельное хранение групп совместимости "
                    f"нарушено (найдены группы {groups_text})"
                ),
                actual_value=groups_text,
                required_value="одна группа совместимости в хранилище",
            )
        ]
    )


def validate_compatibility(storages: list[StorageBuilding]) -> ValidationResult:
    violations: list[NormativeViolation] = []
    for storage in storages:
        violations.extend(check_storage_compatibility(storage).violations)
    return ValidationResult(violations=violations)
