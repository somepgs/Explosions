"""Этап 14: исправления по итогам обзора кода.

Молниезащита (непокрытые точки — нарушение п. 691), раздел 7 записки (высота вентшахты), детальный чертеж
(фактические габариты здания), генплан DXF (проектные расстояния), значения нарушений в GUI, ссылки на пункты.
GUI-проверки на Qt — в `test_stage14_gui_fixes.py`.
"""

from pathlib import Path

import docx
import ezdxf
import pytest

from explosions_core.calc.geometry import storages_bounds
from explosions_core.calc.lightning_protection import calculate_lightning_protection
from explosions_core.calc.site_plan import site_plan_distances
from explosions_core.domain import (
    CalculationSettings,
    LightningArresterMast,
    LightningZoneType,
    NormativeViolation,
    ProjectDefinition,
    WarehouseDuration,
)
from explosions_core.export.cad.dxf_styles import LAYER_BERM_TOE, LAYER_PERIMETER, LAYER_WALLS
from explosions_core.export.cad.master_plan_dxf import export_master_plan_dxf
from explosions_core.export.project_export import export_project_outputs
from explosions_core.gui.help_texts import FIELD_HELP
from explosions_core.gui.layouts import EXPLOSIVE_LAYOUT
from explosions_core.gui.results_view import fmt, violation_rows
from explosions_core.norms import constants_rk343 as norms
from explosions_core.norms import references
from explosions_core.pipeline import calculate_project
from tests.fixtures.sample_project import build_sample_project_definition

COVERAGE_CODE = "LIGHTNING_ZONE_NOT_COVERED"
VENT_POINT = "Верх дефлектора вентшахты"


def _mast(height_m: float) -> LightningArresterMast:
    return LightningArresterMast(mast_id="M1", x_m=12.0, y_m=0.0, height_h_m=height_m)


def _with_mast_height(definition: ProjectDefinition, height_m: float) -> ProjectDefinition:
    designs = []
    for design in definition.storage_designs:
        spec = design.lightning
        masts = [mast.model_copy(update={"height_h_m": height_m}) for mast in spec.masts]
        designs.append(design.model_copy(update={"lightning": spec.model_copy(update={"masts": masts})}))
    return definition.model_copy(update={"storage_designs": designs})


def _with_duration(definition: ProjectDefinition, duration: WarehouseDuration) -> ProjectDefinition:
    storages = [storage.model_copy(update={"duration": duration}) for storage in definition.project.storages]
    project = definition.project.model_copy(update={"storages": storages})
    return definition.model_copy(update={"project": project})


def _with_project(definition: ProjectDefinition, **values) -> ProjectDefinition:
    return definition.model_copy(update={"project": definition.project.model_copy(update=values)})


# ---------- молниезащита: непокрытые точки — нарушение п. 691 ----------


def test_uncovered_roof_points_are_violation_with_method_clause() -> None:
    result = calculate_lightning_protection([_mast(8.0)], LightningZoneType.ZONE_A, 12.0, 9.0, 6.0, 7.5)

    violation = next(v for v in result.violations if v.code == COVERAGE_CODE)
    assert violation.clause == references.CLAUSE_LIGHTNING_COVERAGE_RD
    assert VENT_POINT in violation.actual_value
    assert result.is_fully_protected is False


def test_coverage_violation_cites_sphere_clause_by_default() -> None:
    result = calculate_lightning_protection([_mast(6.5)], None, 12.0, 9.0, 6.0, 7.5)

    violation = next(v for v in result.violations if v.code == COVERAGE_CODE)
    assert violation.clause == references.CLAUSE_LIGHTNING_COVERAGE_SPHERE


def test_uncovered_optional_protection_is_not_violation() -> None:
    result = calculate_lightning_protection(
        [_mast(8.0)], LightningZoneType.ZONE_A, 12.0, 9.0, 6.0, 7.5, protection_required=False
    )

    assert result.unprotected_points
    assert COVERAGE_CODE not in {v.code for v in result.violations}
    assert result.is_fully_protected is False


def test_low_masts_make_project_noncompliant() -> None:
    result = calculate_project(_with_mast_height(build_sample_project_definition(), 7.0))

    codes = [v.code for v in result.all_violations]
    assert codes.count(COVERAGE_CODE) == 2
    assert result.is_compliant is False


def test_low_masts_of_short_term_storages_give_warnings_only() -> None:
    definition = _with_duration(_with_mast_height(build_sample_project_definition(), 7.0), WarehouseDuration.SHORT_TERM)
    result = calculate_project(definition)

    assert COVERAGE_CODE not in {v.code for v in result.all_violations}
    warnings = [i for i in result.issues if i.module == "lightning" and i.severity == "warning"]
    assert len(warnings) == 2
    assert all(VENT_POINT in warning.message for warning in warnings)


def test_demo_with_sufficient_masts_stays_compliant() -> None:
    assert calculate_project(build_sample_project_definition()).is_compliant is True


def test_checklist_marks_uncovered_lightning_as_violation(tmp_path: Path) -> None:
    result = calculate_project(_with_mast_height(build_sample_project_definition(), 7.0))
    path = export_project_outputs(result, tmp_path, dxf=False, docx=True, json_result=False)[0]

    table = next(t for t in docx.Document(path).tables if t.rows[0].cells[0].text == "Проверка")
    row = next(r for r in table.rows if r.cells[0].text == "Молниезащита хранилищ")
    assert row.cells[2].text == "Нарушение"


# ---------- GUI без Qt: текстовые значения нарушений ----------


def test_violation_rows_keep_text_values() -> None:
    violation = NormativeViolation(
        code="LIGHTNING_REQUIRED",
        clause=references.CLAUSE_LIGHTNING_REQUIRED,
        description="Нет молниезащиты",
        actual_value="не задана",
        required_value="защита от ПУМ",
    )

    row = violation_rows([violation])[0]
    assert row[2] == "не задана"
    assert row[3] == "защита от ПУМ"


def test_fmt_formats_numbers_and_passes_text() -> None:
    assert fmt(2.5) == "2,50"
    assert fmt("B, D") == "B, D"
    assert fmt(None) == "—"


# ---------- раздел 7 записки: заданная высота вентшахты ----------


def test_note_table_7_1_uses_project_vent_height(tmp_path: Path) -> None:
    definition = build_sample_project_definition()
    first = definition.storage_designs[0]
    raised = first.model_copy(update={"lightning": first.lightning.model_copy(update={"vent_height_m": 20.0})})
    definition = definition.model_copy(update={"storage_designs": [raised, *definition.storage_designs[1:]]})
    result = calculate_project(definition)
    assert VENT_POINT in result.lightning_records[0].result.unprotected_points

    path = export_project_outputs(result, tmp_path, dxf=False, docx=True, json_result=False)[0]
    table = next(t for t in docx.Document(path).tables if t.rows[0].cells[1].text == "Контрольная точка")
    vent = next(
        [cell.text for cell in row.cells]
        for row in table.rows[1:]
        if row.cells[0].text == result.project.storages[0].name and row.cells[1].text == VENT_POINT
    )
    assert vent[2] == "20.00"
    assert vent[6] == "Вне зоны защиты"


# ---------- детальный чертеж: фактические габариты здания и толщина стен ----------


def _lwpolylines(path: Path, layer: str) -> list:
    doc = ezdxf.readfile(path, encoding="utf-8")
    return [e for e in doc.modelspace().query("LWPOLYLINE") if e.dxf.layer == layer]


def _max_x(entities) -> float:
    return max(point[0] for entity in entities for point in entity.get_points("xy"))


def test_storage_detail_is_drawn_with_actual_building_size(tmp_path: Path) -> None:
    definition = build_sample_project_definition()
    auto_length = calculate_project(definition).project.storages[0].length_m
    first = definition.project.storages[0].model_copy(update={"length_m": auto_length + 6.0})
    definition = _with_project(definition, storages=[first, *definition.project.storages[1:]])
    result = calculate_project(definition)
    berm = result.berm_records[0]

    export_project_outputs(result, tmp_path, dxf=True, docx=False, json_result=False)
    path = tmp_path / "storage_detail_S1.dxf"

    walls = _lwpolylines(path, LAYER_WALLS)
    assert _max_x(walls) == pytest.approx((auto_length + 6.0) / 2.0, abs=1e-6)
    toe = _lwpolylines(path, LAYER_BERM_TOE)
    assert _max_x(toe) == pytest.approx(berm.result.outer_footprint_length_m / 2.0, abs=1e-6)


def test_storage_detail_uses_wall_thickness_from_settings(tmp_path: Path) -> None:
    definition = build_sample_project_definition()
    definition = definition.model_copy(update={"settings": CalculationSettings(wall_thickness_m=0.5)})
    result = calculate_project(definition)
    assert result.settings.wall_thickness_m == pytest.approx(0.5)
    length = result.project.storages[0].length_m

    export_project_outputs(result, tmp_path, dxf=True, docx=False, json_result=False)
    walls = _lwpolylines(tmp_path / "storage_detail_S1.dxf", LAYER_WALLS)
    inner = [e for e in walls if e.closed]
    assert _max_x(inner) == pytest.approx(length / 2.0 - 0.5, abs=1e-6)


# ---------- генплан: проектные расстояния вместо нормативных минимумов ----------


def _perimeter_min_xs(path: Path) -> set[float]:
    return {
        round(min(point[0] for point in entity.get_points("xy")), 6)
        for entity in _lwpolylines(path, LAYER_PERIMETER)
    }


def _export_plan(definition: ProjectDefinition, path: Path) -> tuple[Path, float]:
    result = calculate_project(definition)
    export_master_plan_dxf(
        result.project, result.detonation_results, result.uvv_results, result.berm_results_by_storage, path
    )
    return path, storages_bounds(result.project.storages)[0]


def test_master_plan_fence_follows_project_distance(tmp_path: Path) -> None:
    definition = _with_project(build_sample_project_definition(), fence_to_nearest_storage_m=60.0)
    path, bx1 = _export_plan(definition, tmp_path / "plan.dxf")

    min_xs = _perimeter_min_xs(path)
    assert round(bx1 - 60.0, 6) in min_xs
    assert round(bx1 - 60.0 - 50.0, 6) in min_xs
    assert round(bx1 - norms.MIN_DIST_FENCE_TO_STORAGE_M, 6) not in min_xs


def test_master_plan_short_term_defaults_to_clause_621(tmp_path: Path) -> None:
    definition = _with_duration(build_sample_project_definition(), WarehouseDuration.SHORT_TERM)
    definition = _with_project(
        definition,
        fence_to_nearest_storage_m=None,
        forbidden_zone_width_m=None,
        fence_to_tare_storage_m=None,
    )
    path, bx1 = _export_plan(definition, tmp_path / "plan.dxf")

    min_xs = _perimeter_min_xs(path)
    fence_x = round(bx1 - norms.MIN_DIST_FENCE_TO_STORAGE_SHORT_TERM_M, 6)
    assert fence_x in min_xs
    assert round(fence_x - norms.MIN_FORBIDDEN_ZONE_WIDTH_M, 6) not in min_xs
    assert round(bx1 - norms.MIN_OPEN_FIRE_BAN_RADIUS_M, 6) in min_xs


def test_site_plan_distances_fall_back_to_norms() -> None:
    project = build_sample_project_definition().project.model_copy(
        update={
            "fence_to_nearest_storage_m": None,
            "forbidden_zone_width_m": 70.0,
            "fence_to_guardhouse_m": None,
            "fence_to_tare_storage_m": None,
            "open_fire_ban_radius_m": None,
        }
    )
    distances = site_plan_distances(project)

    assert distances.fence_to_storage_m == norms.MIN_DIST_FENCE_TO_STORAGE_M
    assert distances.forbidden_zone_width_m == 70.0
    assert distances.fence_to_guardhouse_m == 70.0
    assert distances.fence_to_tare_storage_m == norms.MIN_DIST_FENCE_TO_TARE_STORAGE_M
    assert distances.open_fire_ban_radius_m == norms.MIN_OPEN_FIRE_BAN_RADIUS_M


# ---------- ссылки на пункты из реестра и тексты подсказок ----------


def test_checklist_norm_column_uses_registry(tmp_path: Path) -> None:
    result = calculate_project(build_sample_project_definition())
    path = export_project_outputs(result, tmp_path, dxf=False, docx=True, json_result=False)[0]

    table = next(t for t in docx.Document(path).tables if t.rows[0].cells[0].text == "Проверка")
    norms_by_check = {row.cells[0].text: row.cells[1].text for row in table.rows[1:]}
    assert norms_by_check["Внутренняя планировка хранилищ"] == references.CLAUSE_LAYOUT
    perimeter = next(text for check, text in norms_by_check.items() if check.startswith("Генплан"))
    assert perimeter == references.CLAUSE_PERIMETER_PERMANENT


def test_tnt_equivalent_coefficient_is_editable_in_gui() -> None:
    assert "tnt_equivalent_coeff" in EXPLOSIVE_LAYOUT.all_fields()
    assert FIELD_HELP["tnt_equivalent_coeff"]


def test_help_texts_match_defaults_and_usage() -> None:
    assert "максимум" in FIELD_HELP["detonation_formula"]
    assert "генплан" not in FIELD_HELP["category"]
    assert "Приложению 3" in FIELD_HELP["hazard_subclass"]
