"""Безопасные расстояния по действию УВВ (Глава 3 Приложения 11) и по передаче детонации (Глава 4 Приложения 11) Приказа МИР РК № 343.

Формулы и табличные значения сверены с текстом Приказа в редакции от 02.10.2025:
- УВВ: формулы (10) r_в = K_в·∛Q и (11) r_в = k_в·√Q, коэффициенты и границы применения — таблица 2;
  обвалованные хранилища при 1–2 степени — наружные заряды, выше 2-й — углубленные на свою высоту (п. 10, подпункт 2);
  из диапазона таблицы 2 по умолчанию берется максимум (для наименее прочного объекта, п. 10, подпункт 2);
- передача детонации: формула (19) r_д = K_д·∛Q·∜b, b — меньший размер пассивного заряда (п. 15);
  K_д — таблица 4, обвалованные хранилища приравниваются к углубленным (п. 16);
  расчет в обе стороны, принимается большее; хранилища удлиненной формы по одной оси — не менее
  удвоенной ширины большего хранилища (п. 17); таблица 5 (п. 18); смесь в пассивном заряде — по наиболее
  чувствительному ВМ (п. 19).
Масса в расчетах — масса ВВ в кг (свойства ВВ и тротиловый эквивалент не учитываются, п. 10, подпункт 2).
"""

import json
import math
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from explosions_core.calc.geometry import clear_distance_between, storage_bounds, storage_key
from explosions_core.domain import (
    ChargePlacementType,
    DetonationFormulaType,
    DetonationMaterialClass,
    DetonationPairResult,
    ExplosiveItem,
    ExternalProtectedObject,
    LocationType,
    NormativeViolation,
    StorageBuilding,
    UVVDistanceResult,
    UVVMethod,
)
from explosions_core.norms.constants_rk343 import DEFAULT_STACK_WIDTH_B_M
from explosions_core.norms.references import (
    CLAUSE_DETONATION,
    CLAUSE_DETONATION_MAX_PASSIVE,
    CLAUSE_UVV,
    CLAUSE_UVV_TABLE_3,
)

DEFAULT_TABLES_PATH = Path(__file__).resolve().parents[1] / "norms" / "data" / "appendix11_tables_rk343.json"
FORMULA_10 = "r_в = K_в * Q^(1/3)"
FORMULA_11 = "r_в = k_в * Q^(1/2)"
FORMULA_19 = "r_д = K_д * Q^(1/3) * b^(1/4)"
MAX_UVV_DAMAGE_DEGREE_FOR_OPEN_BERMED = 2


@lru_cache(maxsize=None)
def _load_cached(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_appendix11_tables(path: Path | None = None) -> dict:
    return deepcopy(_load_cached((path if path is not None else DEFAULT_TABLES_PATH).resolve()))


def calculate_explosive_mass(items: list[ExplosiveItem]) -> float:
    """Суммарная масса ВВ (кг) в хранилище для расчетов по Приложению 11."""
    return sum(item.net_explosive_mass_kg for item in items)


def calculate_tnt_equivalent_mass(items: list[ExplosiveItem], *, skip_missing: bool = False) -> float:
    """Тротиловый эквивалент (кг). Справочная величина для записки; в расчетах Приложения 11 не используется."""
    total = 0.0
    for item in items:
        if item.tnt_equivalent_coeff is None:
            if skip_missing:
                continue
            raise ValueError(f"Не задан коэффициент ТНТ-эквивалента для партии '{item.name}'")
        total += item.net_explosive_mass_kg * item.tnt_equivalent_coeff
    return total


def _check_supported_location(storage: StorageBuilding) -> None:
    if storage.location_type == LocationType.UNDERGROUND:
        raise ValueError(
            f"Хранилище '{storage_key(storage)}': подземные склады не рассчитываются по главам 3–4 Приложения 11"
        )


def uvv_charge_placement(storage: StorageBuilding, damage_degree: int) -> ChargePlacementType:
    """Расположение заряда для таблицы 2 (п. 10, подпункт 2 Приложения 11).

    Углубленное хранилище — заряд, углубленный на свою высоту. Обвалованное — наружный заряд при 1–2 степени,
    углубленный при степени выше 2-й. Поверхностное и полууглубленное необвалованное — наружный (открытый) заряд.
    """
    _check_supported_location(storage)
    if storage.location_type == LocationType.BURIED:
        return ChargePlacementType.BURIED_OWN_HEIGHT
    if storage.is_bermed and damage_degree > MAX_UVV_DAMAGE_DEGREE_FOR_OPEN_BERMED:
        return ChargePlacementType.BURIED_OWN_HEIGHT
    return ChargePlacementType.OPEN_SURFACE


def detonation_charge_placement(storage: StorageBuilding) -> ChargePlacementType:
    """Расположение заряда для таблицы 4: обвалованные и углубленные — углубленные, прочие — открытые (п. 16)."""
    _check_supported_location(storage)
    if storage.is_bermed or storage.location_type == LocationType.BURIED:
        return ChargePlacementType.BURIED_OWN_HEIGHT
    return ChargePlacementType.OPEN_SURFACE


def storage_detonation_classes(storage: StorageBuilding) -> dict[DetonationMaterialClass, float]:
    """Массы ВВ по классам ВМ таблицы 4."""
    masses: dict[DetonationMaterialClass, float] = {}
    for item in storage.items:
        if item.detonation_class is None:
            raise ValueError(
                f"Партия '{item.name}': не задан класс ВМ по таблице 4 Приложения 11 (detonation_class)"
            )
        masses[item.detonation_class] = masses.get(item.detonation_class, 0.0) + item.net_explosive_mass_kg
    if not masses:
        raise ValueError(f"Хранилище '{storage_key(storage)}' не содержит ВМ")
    return masses


def _placement_key(placement: ChargePlacementType) -> str:
    return "open" if placement == ChargePlacementType.OPEN_SURFACE else "buried"


def uvv_coefficient_and_formula(
    damage_degree: int,
    placement: ChargePlacementType,
    mass_kg: float,
    tables: dict,
) -> tuple[str, float, tuple[float, float]]:
    """Формула, коэффициент (максимум диапазона) и диапазон по таблице 2 Приложения 11."""
    degree = tables["table_2_uvv"].get(str(damage_degree))
    if degree is None:
        raise ValueError(f"Степень повреждения {damage_degree} отсутствует в таблице 2 Приложения 11")
    entry = degree[_placement_key(placement)]
    threshold_t = entry.get("formula_10_above_t")
    if threshold_t is not None and mass_kg > threshold_t * 1000.0:
        formula, low_high = FORMULA_10, entry["K_v"]
    else:
        formula, low_high = FORMULA_11, entry["k_v"]
    low, high = float(low_high[0]), float(low_high[1])
    return formula, high, (low, high)


def uvv_distance(formula: str, coeff: float, mass_kg: float) -> float:
    if formula == FORMULA_10:
        return coeff * mass_kg ** (1.0 / 3.0)
    return coeff * math.sqrt(mass_kg)


def calculate_uvv_safe_distance(
    storage_id: str,
    external_object: ExternalProtectedObject,
    explosive_mass_kg: float,
    placement: ChargePlacementType = ChargePlacementType.OPEN_SURFACE,
    tables: dict | None = None,
) -> UVVDistanceResult:
    tables = tables if tables is not None else load_appendix11_tables()
    formula, coeff, kv_range = uvv_coefficient_and_formula(
        external_object.allowed_damage_degree, placement, explosive_mass_kg, tables
    )
    if external_object.custom_kv_override is not None:
        coeff = external_object.custom_kv_override
    required = uvv_distance(formula, coeff, explosive_mass_kg) * external_object.topography_reduction_coeff

    actual = external_object.actual_distance_m
    violations: list[NormativeViolation] = []
    if actual < required:
        violations.append(
            NormativeViolation(
                code="UVV_SAFE_DISTANCE",
                clause=CLAUSE_UVV,
                description=(
                    f"Хранилище '{storage_id}' — объект '{external_object.name}': фактическое расстояние "
                    f"меньше безопасного по действию УВВ"
                ),
                actual_value=actual,
                required_value=required,
            )
        )
    return UVVDistanceResult(
        storage_id=storage_id,
        object_id=external_object.object_id,
        explosive_mass_kg=explosive_mass_kg,
        placement=placement,
        formula_used=formula,
        kv_range=kv_range,
        applied_coeff=coeff,
        required_distance_m=required,
        actual_distance_m=actual,
        safety_margin_m=actual - required,
        is_safe=not violations,
        violations=violations,
    )


def table3_charge_placement(storage: StorageBuilding) -> ChargePlacementType:
    """Таблица 3: «углубленные (обвалованные)» или «открыто расположенные» хранилища."""
    _check_supported_location(storage)
    if storage.is_bermed or storage.location_type == LocationType.BURIED:
        return ChargePlacementType.BURIED_OWN_HEIGHT
    return ChargePlacementType.OPEN_SURFACE


def table3_uvv_distance(
    object_category: int,
    placement: ChargePlacementType,
    explosive_mass_kg: float,
    tables: dict,
) -> tuple[str, float, float]:
    """(формула, коэффициент, расстояние м) по расчетным формулам таблицы 3 Приложения 11."""
    table = tables["table_3_uvv"]
    category = table["categories"].get(str(object_category))
    if category is None:
        raise ValueError(f"Категория объекта {object_category} отсутствует в таблице 3 Приложения 11")
    row = category.get(_placement_key(placement))
    if row is None:
        raise ValueError(
            f"Таблица 3 Приложения 11 не содержит значений для объектов категории {object_category} "
            "и открыто расположенных хранилищ; используйте таблицу 2"
        )
    max_mass = max(table["masses_kg"])
    if explosive_mass_kg > max_mass:
        raise ValueError(
            f"Масса {explosive_mass_kg:.0f} кг больше предела таблицы 3 ({max_mass} кг); используйте таблицу 2"
        )
    for item in row["formulas"]:
        if item["max_kg"] is None or explosive_mass_kg <= item["max_kg"]:
            coeff = float(item["k"])
            if item["type"] == "sqrt":
                return FORMULA_11, coeff, coeff * math.sqrt(explosive_mass_kg)
            return FORMULA_10, coeff, coeff * explosive_mass_kg ** (1.0 / 3.0)
    raise ValueError("Некорректная строка таблицы 3 в справочнике")


def calculate_uvv_table3_distance(
    storage_id: str,
    external_object: ExternalProtectedObject,
    explosive_mass_kg: float,
    placement: ChargePlacementType,
    tables: dict | None = None,
) -> UVVDistanceResult:
    """Проверка расстояния до объекта по таблице 3 Приложения 11 (п. 10, подпункт 7)."""
    tables = tables if tables is not None else load_appendix11_tables()
    if external_object.table3_object_category is None:
        raise ValueError(
            f"Объект '{external_object.object_id}': не задана категория по таблице 3 (table3_object_category)"
        )
    formula, coeff, required = table3_uvv_distance(
        external_object.table3_object_category, placement, explosive_mass_kg, tables
    )
    actual = external_object.actual_distance_m
    violations: list[NormativeViolation] = []
    if actual < required:
        violations.append(
            NormativeViolation(
                code="UVV_SAFE_DISTANCE_TABLE_3",
                clause=CLAUSE_UVV_TABLE_3,
                description=(
                    f"Хранилище '{storage_id}' — объект '{external_object.name}': фактическое расстояние "
                    "меньше допустимого по таблице 3"
                ),
                actual_value=actual,
                required_value=required,
            )
        )
    return UVVDistanceResult(
        storage_id=storage_id,
        object_id=external_object.object_id,
        method=UVVMethod.TABLE_3,
        explosive_mass_kg=explosive_mass_kg,
        placement=placement,
        formula_used=formula,
        kv_range=None,
        applied_coeff=coeff,
        required_distance_m=required,
        actual_distance_m=actual,
        safety_margin_m=actual - required,
        is_safe=not violations,
        violations=violations,
    )


def kd_from_table_4(
    active_class: DetonationMaterialClass,
    active_placement: ChargePlacementType,
    passive_class: DetonationMaterialClass,
    passive_placement: ChargePlacementType,
    tables: dict,
) -> float:
    row = tables["table_4_kd"][f"{active_class.value}_{_placement_key(active_placement)}"]
    return float(row[f"{passive_class.value}_{_placement_key(passive_placement)}"])


def get_kd(
    active_classes: dict[DetonationMaterialClass, float],
    active_placement: ChargePlacementType,
    passive_classes: dict[DetonationMaterialClass, float],
    passive_placement: ChargePlacementType,
    tables: dict,
) -> float:
    """K_д по таблице 4.

    Пассивный заряд из разных ВМ — по ВМ с наибольшей чувствительностью к детонации (п. 19): по таблице 4 это ВМ,
    дающий наибольший K_д. Активный заряд из разных ВМ п. 19 не регулирует — принимается наибольший K_д (допущение,
    в запас надежности).
    """
    return max(
        kd_from_table_4(active, active_placement, passive, passive_placement, tables)
        for active in active_classes
        for passive in passive_classes
    )


def calculate_detonation_distance(explosive_mass_kg: float, k_d: float, passive_width_b_m: float) -> float:
    """Формула (19) Приложения 11: r_д = K_д · Q^(1/3) · b^(1/4)."""
    if passive_width_b_m <= 0:
        raise ValueError("Ширина пассивного заряда b должна быть больше нуля")
    return k_d * explosive_mass_kg ** (1.0 / 3.0) * passive_width_b_m ** 0.25


def table_5_distance(
    active_classes: dict[DetonationMaterialClass, float],
    active_placement: ChargePlacementType,
    passive_classes: dict[DetonationMaterialClass, float],
    passive_placement: ChargePlacementType,
    explosive_mass_kg: float,
    passive_width_b_m: float,
    tables: dict,
) -> float | None:
    """Расстояние по таблице 5 (b = 1,6 м, 10–420 т) с линейной интерполяцией по массе.

    None — если таблица неприменима (другая ширина b, масса вне диапазона или пары ВМ нет в таблице).
    """
    if abs(passive_width_b_m - DEFAULT_STACK_WIDTH_B_M) > 1e-9:
        return None
    mass_t = explosive_mass_kg / 1000.0
    candidates: list[float] = []
    for active in active_classes:
        for passive in passive_classes:
            active_key = f"{active.value}_{_placement_key(active_placement)}"
            passive_key = f"{passive.value}_{_placement_key(passive_placement)}"
            for row in tables["table_5_rd_b_1_6_m"]:
                if row["active"] == active_key and row["passive"] == passive_key:
                    value = _interpolate(mass_t, row["distances_m"])
                    if value is not None:
                        candidates.append(value)
    return max(candidates) if candidates else None


def _interpolate(mass_t: float, distances: dict[str, float]) -> float | None:
    points = sorted((float(mass), float(dist)) for mass, dist in distances.items())
    if mass_t < points[0][0] or mass_t > points[-1][0]:
        return None
    for (m1, d1), (m2, d2) in zip(points, points[1:]):
        if m1 <= mass_t <= m2:
            return d1 + (d2 - d1) * (mass_t - m1) / (m2 - m1)
    return points[-1][1]


def passive_width_b(storage: StorageBuilding) -> float:
    return storage.stack_width_b_m if storage.stack_width_b_m is not None else DEFAULT_STACK_WIDTH_B_M


def _direction(
    active: StorageBuilding,
    passive: StorageBuilding,
    formula: DetonationFormulaType,
    tables: dict,
) -> tuple[float, float, float]:
    """(K_д, Q активного, r_д) для направления активный -> пассивный."""
    active_classes = storage_detonation_classes(active)
    passive_classes = storage_detonation_classes(passive)
    active_placement = detonation_charge_placement(active)
    passive_placement = detonation_charge_placement(passive)
    k_d = get_kd(active_classes, active_placement, passive_classes, passive_placement, tables)
    q_active = calculate_explosive_mass(active.items)
    b = passive_width_b(passive)
    by_formula = calculate_detonation_distance(q_active, k_d, b)
    by_table = table_5_distance(active_classes, active_placement, passive_classes, passive_placement, q_active, b, tables)
    if formula == DetonationFormulaType.FORMULA_19:
        r_d = by_formula
    elif formula == DetonationFormulaType.TABLE_5:
        if by_table is None:
            raise ValueError(
                f"Таблица 5 неприменима для пары '{storage_key(active)}' -> '{storage_key(passive)}' "
                f"(b = {b} м, Q = {q_active / 1000.0:.1f} т); используйте формулу (19)"
            )
        r_d = by_table
    else:
        r_d = max(by_formula, by_table) if by_table is not None else by_formula
    return k_d, q_active, r_d


def axial_min_distance(storage_i: StorageBuilding, storage_j: StorageBuilding) -> float | None:
    """п. 17: хранилища удлиненной формы по одной оси — не менее удвоенной ширины большего хранилища.

    Хранилища считаются расположенными по одной оси, если оба вытянуты вдоль одной координатной оси и
    их проекции на перпендикулярную ось перекрываются. Иначе — None (правило не применяется).
    """
    if None in (storage_i.length_m, storage_i.width_m, storage_j.length_m, storage_j.width_m):
        return None
    i_x1, i_y1, i_x2, i_y2 = storage_bounds(storage_i)
    j_x1, j_y1, j_x2, j_y2 = storage_bounds(storage_j)
    i_along_x = storage_i.length_m > storage_i.width_m
    j_along_x = storage_j.length_m > storage_j.width_m
    i_along_y = storage_i.width_m > storage_i.length_m
    j_along_y = storage_j.width_m > storage_j.length_m
    if i_along_x and j_along_x and min(i_y2, j_y2) > max(i_y1, j_y1):
        return 2.0 * max(storage_i.width_m, storage_j.width_m)
    if i_along_y and j_along_y and min(i_x2, j_x2) > max(i_x1, j_x1):
        return 2.0 * max(storage_i.length_m, storage_j.length_m)
    return None


def calculate_clear_distance(storage_i: StorageBuilding, storage_j: StorageBuilding) -> float:
    return clear_distance_between(storage_i, storage_j)


def calculate_detonation_distance_pair(
    storage_i: StorageBuilding,
    storage_j: StorageBuilding,
    *,
    formula: DetonationFormulaType = DetonationFormulaType.MAX_CONSERVATIVE,
    tables: dict | None = None,
) -> DetonationPairResult:
    """Передача детонации между двумя хранилищами (п. 15–19 Приложения 11)."""
    tables = tables if tables is not None else load_appendix11_tables()
    k_ij, q_i, r_i_to_j = _direction(storage_i, storage_j, formula, tables)
    k_ji, q_j, r_j_to_i = _direction(storage_j, storage_i, formula, tables)
    axial = axial_min_distance(storage_i, storage_j)
    governing = max(r_i_to_j, r_j_to_i, axial or 0.0)
    actual = clear_distance_between(storage_i, storage_j)

    violations: list[NormativeViolation] = []
    if actual < governing:
        clause = CLAUSE_DETONATION_MAX_PASSIVE if axial is not None and axial >= max(r_i_to_j, r_j_to_i) else CLAUSE_DETONATION
        violations.append(
            NormativeViolation(
                code="DETONATION_TRANSFER_DISTANCE",
                clause=clause,
                description=(
                    f"Хранилища '{storage_key(storage_i)}' и '{storage_key(storage_j)}': расстояние в свету "
                    f"меньше безопасного по передаче детонации"
                ),
                actual_value=actual,
                required_value=governing,
            )
        )
    return DetonationPairResult(
        storage_i_id=storage_key(storage_i),
        storage_j_id=storage_key(storage_j),
        q_i_kg=q_i,
        q_j_kg=q_j,
        k_d_i_to_j=k_ij,
        k_d_j_to_i=k_ji,
        b_i_m=passive_width_b(storage_i),
        b_j_m=passive_width_b(storage_j),
        r_d_i_to_j_m=r_i_to_j,
        r_d_j_to_i_m=r_j_to_i,
        governing_required_r_d_m=governing,
        actual_clear_distance_m=actual,
        axial_min_distance_m=axial,
        is_safe=not violations,
        violations=violations,
    )


class SafeDistanceEngine:
    def __init__(
        self,
        tables: dict | None = None,
        formula: DetonationFormulaType = DetonationFormulaType.MAX_CONSERVATIVE,
        uvv_method: UVVMethod = UVVMethod.TABLE_2_FORMULAS,
    ) -> None:
        self._tables = tables if tables is not None else load_appendix11_tables()
        self._formula = formula
        self._uvv_method = uvv_method

    @property
    def tables(self) -> dict:
        return self._tables

    def uvv(
        self,
        storage: StorageBuilding,
        external_object: ExternalProtectedObject,
        placement: ChargePlacementType | None = None,
        *,
        explosive_mass_kg: float | None = None,
    ) -> UVVDistanceResult:
        mass = explosive_mass_kg if explosive_mass_kg is not None else calculate_explosive_mass(storage.items)
        if self._uvv_method == UVVMethod.TABLE_3:
            chosen = placement if placement is not None else table3_charge_placement(storage)
            return calculate_uvv_table3_distance(storage_key(storage), external_object, mass, chosen, self._tables)
        chosen = placement if placement is not None else uvv_charge_placement(storage, external_object.allowed_damage_degree)
        return calculate_uvv_safe_distance(storage_key(storage), external_object, mass, chosen, self._tables)

    def table3_governing_mass(self, storages: list[StorageBuilding]) -> float:
        """Примечание к таблице 3: расстояния — по вместимости наибольшего хранилища ВМ."""
        return max((calculate_explosive_mass(storage.items) for storage in storages), default=0.0)

    def uvv_matrix(
        self,
        storages: list[StorageBuilding],
        targets: list[ExternalProtectedObject],
        placement: ChargePlacementType | None = None,
    ) -> list[UVVDistanceResult]:
        mass = self.table3_governing_mass(storages) if self._uvv_method == UVVMethod.TABLE_3 else None
        return [
            self.uvv(storage, target, placement, explosive_mass_kg=mass) for storage in storages for target in targets
        ]

    def detonation_pair(self, storage_i: StorageBuilding, storage_j: StorageBuilding) -> DetonationPairResult:
        return calculate_detonation_distance_pair(storage_i, storage_j, formula=self._formula, tables=self._tables)

    def detonation_matrix(self, storages: list[StorageBuilding]) -> list[DetonationPairResult]:
        placed = [storage for storage in storages if storage.x_m is not None and storage.y_m is not None]
        return [
            self.detonation_pair(placed[i], placed[j])
            for i in range(len(placed))
            for j in range(i + 1, len(placed))
        ]
