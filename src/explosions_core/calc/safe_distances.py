"""Безопасные расстояния по действию УВВ (Глава 3 Приложения 11) и по передаче детонации (Глава 4 Приложения 11) Приказа МИР РК № 343."""

import json
import math
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from explosions_core.calc.geometry import clear_distance_between, storage_key
from explosions_core.domain import (
    ChargePlacementType,
    DetonationFormulaType,
    DetonationPairResult,
    ExplosiveItem,
    ExternalProtectedObject,
    LocationType,
    NormativeViolation,
    StorageBuilding,
    UVVDistanceResult,
)
from explosions_core.norms.constants_rk343 import DEFAULT_STACK_WIDTH_B_M, UVV_FORMULA_MASS_THRESHOLD_KG
from explosions_core.norms.references import CLAUSE_DETONATION, CLAUSE_UVV

DEFAULT_TABLES_PATH = Path(__file__).resolve().parents[1] / "norms" / "data" / "appendix11_tables_rk343.json"
NOT_IMPLEMENTED_MESSAGE = "Требуется таблица из Приложения 11 Приказа № 343"


@lru_cache(maxsize=None)
def _load_cached(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_appendix11_tables(path: Path | None = None) -> dict:
    return deepcopy(_load_cached((path if path is not None else DEFAULT_TABLES_PATH).resolve()))


def calculate_tnt_equivalent_mass(items: list[ExplosiveItem], *, skip_missing: bool = False) -> float:
    total = 0.0
    for item in items:
        if item.tnt_equivalent_coeff is None:
            if skip_missing:
                continue
            raise ValueError(f"Не задан коэффициент ТНТ-эквивалента для партии '{item.name}'")
        total += item.net_explosive_mass_kg * item.tnt_equivalent_coeff
    return total


def get_uvv_coefficient(
    damage_degree: int,
    placement: ChargePlacementType,
    q_tnt_kg: float,
    tables: dict | None = None,
    override: float | None = None,
) -> float:
    if override is not None:
        return override
    tables = tables if tables is not None else load_appendix11_tables()
    entry = tables["uvv_damage_degrees"].get(str(damage_degree), {}).get(placement.value)
    if entry is None:
        raise NotImplementedError(NOT_IMPLEMENTED_MESSAGE)
    if q_tnt_kg > UVV_FORMULA_MASS_THRESHOLD_KG:
        value = entry.get("K_v_max")
    else:
        value = entry.get("k_v", entry.get("k_v_max"))
    if value is None:
        raise NotImplementedError(NOT_IMPLEMENTED_MESSAGE)
    return float(value)


def calculate_uvv_safe_distance(
    storage_id: str,
    external_object: ExternalProtectedObject,
    q_tnt_kg: float,
    placement: ChargePlacementType = ChargePlacementType.OPEN_SURFACE,
    tables: dict | None = None,
) -> UVVDistanceResult:
    coeff = get_uvv_coefficient(
        external_object.allowed_damage_degree,
        placement,
        q_tnt_kg,
        tables,
        external_object.custom_kv_override,
    )
    topography = external_object.topography_reduction_coeff
    if q_tnt_kg > UVV_FORMULA_MASS_THRESHOLD_KG:
        formula = "r_в = K_в * Q^(1/3) (Q > 1000 кг)"
        required = coeff * (q_tnt_kg ** (1.0 / 3.0)) * topography
    else:
        formula = "r_в = k_в * Q^(1/2) (Q <= 1000 кг)"
        required = coeff * math.sqrt(q_tnt_kg) * topography

    actual = external_object.actual_distance_m
    violations: list[NormativeViolation] = []
    if actual < required:
        violations.append(
            NormativeViolation(
                code="UVV_SAFE_DISTANCE",
                clause=CLAUSE_UVV,
                description="Фактическое расстояние до охраняемого объекта меньше безопасного по действию УВВ",
                actual_value=actual,
                required_value=required,
            )
        )
    return UVVDistanceResult(
        storage_id=storage_id,
        object_id=external_object.object_id,
        equivalent_tnt_mass_kg=q_tnt_kg,
        formula_used=formula,
        applied_coeff_kv=coeff,
        required_distance_m=required,
        actual_distance_m=actual,
        safety_margin_m=actual - required,
        is_safe=not violations,
        violations=violations,
    )


def interpolate_from_normative_table(mass_kg: float, grid: list[dict]) -> float:
    if not grid:
        raise ValueError("Табличная сетка Приложения 11 пуста")
    points = sorted(grid, key=lambda point: point["mass_kg"])
    if mass_kg < points[0]["mass_kg"] or mass_kg > points[-1]["mass_kg"]:
        raise ValueError(f"Масса {mass_kg} кг вне диапазона табличной сетки Приложения 11")
    for left, right in zip(points, points[1:]):
        if left["mass_kg"] <= mass_kg <= right["mass_kg"]:
            span = right["mass_kg"] - left["mass_kg"]
            if span == 0:
                return left["distance_m"]
            ratio = (mass_kg - left["mass_kg"]) / span
            return left["distance_m"] + ratio * (right["distance_m"] - left["distance_m"])
    return points[-1]["distance_m"]


def calculate_detonation_distance(
    q_tnt_kg: float,
    k_d: float,
    b_m: float,
    formula: DetonationFormulaType = DetonationFormulaType.MAX_CONSERVATIVE,
    grid: list[dict] | None = None,
) -> float:
    if b_m <= 0:
        raise ValueError("Ширина штабеля b должна быть больше нуля")
    r_18 = k_d * (q_tnt_kg ** (1.0 / 3.0))
    r_19 = k_d * math.sqrt(q_tnt_kg * b_m) / b_m
    if formula == DetonationFormulaType.FORMULA_18_CUBIC:
        return r_18
    if formula == DetonationFormulaType.FORMULA_19_STACK_WIDTH:
        return r_19
    candidates = [r_18, r_19]
    if grid:
        candidates.append(interpolate_from_normative_table(q_tnt_kg, grid))
    return max(candidates)


def select_detonation_profile(
    active: StorageBuilding,
    passive: StorageBuilding,
    *,
    high_sensitivity: bool = False,
    granular_asvv: bool = False,
) -> str:
    active_buried = active.location_type == LocationType.BURIED
    passive_buried = passive.location_type == LocationType.BURIED
    if active_buried and passive_buried:
        return "BURIED_TO_BURIED"
    if active_buried or passive_buried:
        raise NotImplementedError("Смешанная пара углубленного и наземного хранилища не описана в таблице K_д Приложения 11")
    if not active.is_bermed and not passive.is_bermed:
        return "UNBERMED_TO_UNBERMED_HIGH_SENS" if high_sensitivity else "UNBERMED_TO_UNBERMED_STANDARD"
    if not active.is_bermed and passive.is_bermed:
        return "UNBERMED_TO_BERMED"
    if active.is_bermed and not passive.is_bermed:
        return "BERMED_TO_UNBERMED"
    return "BERMED_TO_BERMED_GRANULAR" if granular_asvv else "BERMED_TO_BERMED_STANDARD"


def _direction_distance(
    active: StorageBuilding,
    passive: StorageBuilding,
    formula: DetonationFormulaType,
    tables: dict,
    grid: list[dict] | None,
    high_sensitivity: bool,
    granular_asvv: bool,
) -> tuple[float, float]:
    q_tnt = calculate_tnt_equivalent_mass(active.items)
    b_m = active.stack_width_b_m if active.stack_width_b_m is not None else DEFAULT_STACK_WIDTH_B_M
    profile = select_detonation_profile(
        active, passive, high_sensitivity=high_sensitivity, granular_asvv=granular_asvv
    )
    k_d = tables["detonation_coefficients_kd"]["profiles"][profile]
    return q_tnt, calculate_detonation_distance(q_tnt, k_d, b_m, formula, grid)


def calculate_clear_distance(storage_i: StorageBuilding, storage_j: StorageBuilding) -> float:
    return clear_distance_between(storage_i, storage_j)


def calculate_detonation_distance_pair(
    storage_i: StorageBuilding,
    storage_j: StorageBuilding,
    *,
    formula: DetonationFormulaType = DetonationFormulaType.MAX_CONSERVATIVE,
    tables: dict | None = None,
    grid: list[dict] | None = None,
    high_sensitivity: bool = False,
    granular_asvv: bool = False,
) -> DetonationPairResult:
    tables = tables if tables is not None else load_appendix11_tables()
    grid = grid if grid is not None else (tables.get("tabular_lookup_grids") or None)
    q_i, r_i_to_j = _direction_distance(storage_i, storage_j, formula, tables, grid, high_sensitivity, granular_asvv)
    q_j, r_j_to_i = _direction_distance(storage_j, storage_i, formula, tables, grid, high_sensitivity, granular_asvv)
    governing = max(r_i_to_j, r_j_to_i)
    actual = clear_distance_between(storage_i, storage_j)

    violations: list[NormativeViolation] = []
    if actual < governing:
        violations.append(
            NormativeViolation(
                code="DETONATION_TRANSFER_DISTANCE",
                clause=CLAUSE_DETONATION,
                description="Фактическое расстояние в свету между хранилищами меньше допустимого по передаче детонации",
                actual_value=actual,
                required_value=governing,
            )
        )
    return DetonationPairResult(
        storage_i_id=storage_key(storage_i),
        storage_j_id=storage_key(storage_j),
        q_i_tnt_kg=q_i,
        q_j_tnt_kg=q_j,
        r_d_i_to_j_m=r_i_to_j,
        r_d_j_to_i_m=r_j_to_i,
        governing_required_r_d_m=governing,
        actual_clear_distance_m=actual,
        is_safe=not violations,
        violations=violations,
    )


class SafeDistanceEngine:
    def __init__(self, tables: dict | None = None) -> None:
        self._tables = tables if tables is not None else load_appendix11_tables()

    def uvv(
        self,
        storage: StorageBuilding,
        external_object: ExternalProtectedObject,
        placement: ChargePlacementType = ChargePlacementType.OPEN_SURFACE,
    ) -> UVVDistanceResult:
        q_tnt = calculate_tnt_equivalent_mass(storage.items)
        return calculate_uvv_safe_distance(storage_key(storage), external_object, q_tnt, placement, self._tables)

    def uvv_matrix(
        self,
        storages: list[StorageBuilding],
        targets: list[ExternalProtectedObject],
        placement: ChargePlacementType = ChargePlacementType.OPEN_SURFACE,
    ) -> list[UVVDistanceResult]:
        return [self.uvv(storage, target, placement) for storage in storages for target in targets]

    def detonation_pair(
        self,
        storage_i: StorageBuilding,
        storage_j: StorageBuilding,
        *,
        formula: DetonationFormulaType = DetonationFormulaType.MAX_CONSERVATIVE,
        high_sensitivity: bool = False,
        granular_asvv: bool = False,
    ) -> DetonationPairResult:
        return calculate_detonation_distance_pair(
            storage_i,
            storage_j,
            formula=formula,
            tables=self._tables,
            high_sensitivity=high_sensitivity,
            granular_asvv=granular_asvv,
        )

    def detonation_matrix(
        self,
        storages: list[StorageBuilding],
        *,
        formula: DetonationFormulaType = DetonationFormulaType.MAX_CONSERVATIVE,
        high_sensitivity: bool = False,
        granular_asvv: bool = False,
    ) -> list[DetonationPairResult]:
        placed = [storage for storage in storages if storage.x_m is not None and storage.y_m is not None]
        return [
            self.detonation_pair(
                placed[i],
                placed[j],
                formula=formula,
                high_sensitivity=high_sensitivity,
                granular_asvv=granular_asvv,
            )
            for i in range(len(placed))
            for j in range(i + 1, len(placed))
        ]
