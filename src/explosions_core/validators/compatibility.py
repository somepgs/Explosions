"""Модуль 1: раздельное хранение ВМ разных групп совместимости (п. 8, Приложение 2) с исключениями п. 9 Приказа № 343.

п. 9 допускает совместное хранение:
1) дымных (группа D) и бездымных (группа C) порохов;
2) огнепроводного шнура, средств его зажигания, порохов, сигнальных и пороховых патронов, сигнальных ракет
   (группа G) с ВМ групп B, C и D;
3) детонирующего шнура и детонирующей ленты (группа D) с капсюль-детонаторами, электродетонаторами и
   пиротехническими реле (группа B).

Классификационные шифры (подкласс + группа) проверяются по Приложению 3 ТР ТС 028/2012.
"""

from itertools import combinations

from explosions_core.domain import (
    CompatibilityGroup,
    ExplosiveItem,
    NormativeViolation,
    StorageBuilding,
    ValidationResult,
)
from explosions_core.norms.references import (
    CLAUSE_COMPATIBILITY,
    CLAUSE_COMPATIBILITY_EXCEPTION,
    CLAUSE_TR_TS_CLASSIFICATION,
)

G_COMPATIBLE_GROUPS = frozenset({CompatibilityGroup.B, CompatibilityGroup.C, CompatibilityGroup.D})

# Приложение 3 ТР ТС 028/2012: допустимые подклассы по группам совместимости.
# Для группы C шифры в Приложении 3 не указаны (не проверяется); группы A в регламенте нет.
TR_TS_CLASSIFICATION_CODES: dict[CompatibilityGroup, frozenset[str]] = {
    CompatibilityGroup.B: frozenset({"1.1", "1.2", "1.4"}),
    CompatibilityGroup.D: frozenset({"1.1", "1.2", "1.4", "1.5"}),
    CompatibilityGroup.E: frozenset({"1.1", "1.2", "1.4"}),
    CompatibilityGroup.F: frozenset({"1.1", "1.2", "1.3", "1.4"}),
    CompatibilityGroup.G: frozenset({"1.1", "1.2", "1.3", "1.4"}),
    CompatibilityGroup.S: frozenset({"1.4"}),
    CompatibilityGroup.N: frozenset({"1.6"}),
}
GROUPS_WITHOUT_CODES = frozenset({CompatibilityGroup.C})


def check_classification_codes(storage: StorageBuilding) -> ValidationResult:
    """Шифр «подкласс + группа» каждой партии — по Приложению 3 ТР ТС 028/2012; без подкласса проверяется только группа."""
    violations: list[NormativeViolation] = []
    for item in storage.items:
        if item.group == CompatibilityGroup.A:
            violations.append(
                NormativeViolation(
                    code="CLASSIFICATION_CODE_INVALID",
                    clause=CLAUSE_TR_TS_CLASSIFICATION,
                    description=(
                        f"Хранилище '{storage.name}', партия '{item.name}': группа совместимости A "
                        "отсутствует в ТР ТС 028/2012"
                    ),
                    actual_value="A",
                    required_value="группа по Приложению 3 ТР ТС 028/2012",
                )
            )
            continue
        if item.hazard_subclass is None or item.group in GROUPS_WITHOUT_CODES:
            continue
        allowed = TR_TS_CLASSIFICATION_CODES.get(item.group, frozenset())
        subclass = item.hazard_subclass.strip()
        if subclass not in allowed:
            violations.append(
                NormativeViolation(
                    code="CLASSIFICATION_CODE_INVALID",
                    clause=CLAUSE_TR_TS_CLASSIFICATION,
                    description=(
                        f"Хранилище '{storage.name}', партия '{item.name}': шифр {subclass}{item.group.value} "
                        "отсутствует в Приложении 3 ТР ТС 028/2012"
                    ),
                    actual_value=f"{subclass}{item.group.value}",
                    required_value=", ".join(f"{code}{item.group.value}" for code in sorted(allowed)),
                )
            )
    return ValidationResult(violations=violations)


def _items_of(items: list[ExplosiveItem], group: CompatibilityGroup) -> list[ExplosiveItem]:
    return [item for item in items if item.group == group]


def _is_allowed_pair(items: list[ExplosiveItem], first: CompatibilityGroup, second: CompatibilityGroup) -> bool:
    pair = {first, second}
    if CompatibilityGroup.G in pair:
        return not (pair - {CompatibilityGroup.G}) - G_COMPATIBLE_GROUPS
    if pair == {CompatibilityGroup.C, CompatibilityGroup.D}:
        return all(item.is_black_powder for item in _items_of(items, CompatibilityGroup.D)) and all(
            item.is_smokeless_powder for item in _items_of(items, CompatibilityGroup.C)
        )
    if pair == {CompatibilityGroup.B, CompatibilityGroup.D}:
        return all(item.is_detonating_cord for item in _items_of(items, CompatibilityGroup.D)) and all(
            item.is_initiating_device for item in _items_of(items, CompatibilityGroup.B)
        )
    return False


def check_storage_compatibility(storage: StorageBuilding) -> ValidationResult:
    groups = sorted({item.group for item in storage.items}, key=lambda group: group.value)
    if len(groups) <= 1:
        return ValidationResult()
    forbidden = [
        f"{first.value}+{second.value}"
        for first, second in combinations(groups, 2)
        if not _is_allowed_pair(storage.items, first, second)
    ]
    if not forbidden:
        return ValidationResult()
    groups_text = ", ".join(group.value for group in groups)
    return ValidationResult(
        violations=[
            NormativeViolation(
                code="COMPAT_MIXED_GROUPS",
                clause=CLAUSE_COMPATIBILITY,
                description=(
                    f"Хранилище '{storage.name}': ВМ различных групп совместимости хранятся совместно "
                    f"(группы {groups_text}); сочетания {', '.join(forbidden)} не подпадают под исключения "
                    f"{CLAUSE_COMPATIBILITY_EXCEPTION}"
                ),
                actual_value=groups_text,
                required_value="раздельное хранение групп совместимости",
            )
        ]
    )


def validate_compatibility(storages: list[StorageBuilding]) -> ValidationResult:
    violations: list[NormativeViolation] = []
    for storage in storages:
        violations.extend(check_storage_compatibility(storage).violations)
        violations.extend(check_classification_codes(storage).violations)
    return ValidationResult(violations=violations)
