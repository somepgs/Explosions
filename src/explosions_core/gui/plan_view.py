"""Предпросмотр генплана: хранилища, ограда и окружности безопасных расстояний (PySide6).

Координаты берутся из модели проекта (`x_m`, `y_m` — левый нижний угол здания), ось Y направлена вверх.
Вид только отображает данные; расчет выполняется в ядре, здесь значения не пересчитываются.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QGraphicsEllipseItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from explosions_core.calc.geometry import offset_bounds, storage_bounds, storages_bounds
from explosions_core.calc.site_plan import site_plan_distances
from explosions_core.domain import DetonationPairResult, ProjectCalculationResult, UVVDistanceResult, WarehouseProjectInput
from explosions_core.domain.storage import StorageBuilding
from explosions_core.gui.results_view import fmt

ZONE_FENCE_LABEL = "Ограда (от хранилищ ВМ)"
COLOR_STORAGE_OK = QColor("#2E7D32")
COLOR_STORAGE_FAIL = QColor("#C62828")
COLOR_FENCE = QColor("#6D4C41")
COLOR_RD = QColor("#7B1FA2")
COLOR_UVV = QColor("#1565C0")
MIN_ZOOM = 0.05
MAX_ZOOM = 50.0


def is_placed(storage: StorageBuilding) -> bool:
    """Хранилище можно нарисовать: заданы координаты и размеры здания."""
    return (
        storage.x_m is not None
        and storage.y_m is not None
        and storage.length_m is not None
        and storage.width_m is not None
    )


def _failed_storage_ids(result: ProjectCalculationResult | None) -> set[str]:
    if result is None:
        return set()
    failed: set[str] = set()
    for pair in result.detonation_results:
        if not pair.is_safe:
            failed.update({pair.storage_i_id, pair.storage_j_id})
    for uvv in result.uvv_results:
        if not uvv.is_safe:
            failed.add(uvv.storage_id)
    return failed


class PlanView(QWidget):
    """Окно генплана с флажками слоев и масштабированием колесом мыши."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._view = QGraphicsView(self._scene, self)
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._view.setBackgroundBrush(QBrush(QColor("#FAFAFA")))
        self._show_rd = QCheckBox("Радиусы r_д", self)
        self._show_uvv = QCheckBox("Радиусы R_увв", self)
        self._show_fence = QCheckBox("Ограда и зоны", self)
        for box in (self._show_rd, self._show_uvv, self._show_fence):
            box.setChecked(True)
            box.toggled.connect(self._redraw)
        self._project: WarehouseProjectInput | None = None
        self._result: ProjectCalculationResult | None = None
        self._layers_row = QHBoxLayout()
        self._layers_row.addWidget(self._show_rd)
        self._layers_row.addWidget(self._show_uvv)
        self._layers_row.addWidget(self._show_fence)
        self._layers_row.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._layers_row)
        layout.addWidget(self._view, 1)
        self._view.setMinimumSize(480, 360)

    def set_data(self, project: WarehouseProjectInput, result: ProjectCalculationResult | None) -> None:
        self._project = project
        self._result = result
        self._redraw()

    def fit(self) -> None:
        rect = self._scene.itemsBoundingRect()
        if rect.isNull():
            return
        self._view.fitInView(rect.adjusted(-20, -20, 20, 20), Qt.AspectRatioMode.KeepAspectRatio)

    def zoom_by(self, factor: float) -> None:
        current = self._view.transform().m11()
        target = current * factor
        if MIN_ZOOM <= target <= MAX_ZOOM:
            self._view.scale(factor, factor)

    def wheelEvent(self, event) -> None:  # noqa: N802 (имя из Qt)
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.zoom_by(factor)

    def rect_count(self) -> int:
        return sum(1 for item in self._scene.items() if isinstance(item, QGraphicsRectItem))

    def ellipse_count(self) -> int:
        return sum(1 for item in self._scene.items() if isinstance(item, QGraphicsEllipseItem))

    def _redraw(self, *_args) -> None:
        self._scene.clear()
        if self._project is None:
            return
        storages = [s for s in self._project.storages if is_placed(s)]
        if not storages:
            self._scene.addSimpleText(
                "Задайте координаты хранилищ на шаге «4. Размещение и обвалование»\n"
                "и размеры здания (или раздел «Планировка и габариты» на шаге 3)"
            )
            return
        failed = _failed_storage_ids(self._result)
        if self._show_fence.isChecked():
            self._draw_fence(storages, site_plan_distances(self._project).fence_to_storage_m)
        if self._show_rd.isChecked() and self._result is not None:
            self._draw_detonation(self._result.detonation_results, storages)
        if self._show_uvv.isChecked() and self._result is not None:
            self._draw_uvv(self._result.uvv_results, storages)
        for storage in storages:
            self._draw_storage(storage, failed)
        self._scene.setSceneRect(self._scene.itemsBoundingRect().adjusted(-20, -20, 20, 20))
        self.fit()

    def _draw_storage(self, storage: StorageBuilding, failed: set[str]) -> None:
        left, bottom, right, top = storage_bounds(storage)
        key = storage.storage_id or storage.name
        color = COLOR_STORAGE_FAIL if key in failed else COLOR_STORAGE_OK
        rect = QRectF(QPointF(left, -top), QPointF(right, -bottom))
        item = self._scene.addRect(rect, QPen(color, 0.3), QBrush(QColor(color.red(), color.green(), color.blue(), 60)))
        item.setToolTip(f"{storage.name}: {fmt(right - left)} × {fmt(top - bottom)} м")
        label = QGraphicsSimpleTextItem(storage.name)
        label.setPos(left, -top - 1.5)
        label.setBrush(QBrush(color))
        self._scene.addItem(label)

    def _draw_fence(self, storages: list[StorageBuilding], offset_m: float) -> None:
        left, bottom, right, top = offset_bounds(storages_bounds(storages), offset_m)
        self._scene.addRect(
            QRectF(QPointF(left, -top), QPointF(right, -bottom)),
            QPen(COLOR_FENCE, 0.4, Qt.PenStyle.DashLine),
            QBrush(Qt.BrushStyle.NoBrush),
        ).setToolTip(f"{ZONE_FENCE_LABEL}: {fmt(offset_m)} м")

    def _draw_detonation(self, pairs: list[DetonationPairResult], storages: list[StorageBuilding]) -> None:
        centers = {(s.storage_id or s.name): self._center(s) for s in storages}
        for pair in pairs:
            for key, radius in (
                (pair.storage_i_id, pair.r_d_i_to_j_m),
                (pair.storage_j_id, pair.r_d_j_to_i_m),
            ):
                if key not in centers:
                    continue
                cx, cy = centers[key]
                self._circle(cx, cy, radius, COLOR_RD, f"r_д = {fmt(radius)} м ({key})")

    def _draw_uvv(self, results: list[UVVDistanceResult], storages: list[StorageBuilding]) -> None:
        centers = {(s.storage_id or s.name): self._center(s) for s in storages}
        for item in results:
            if item.storage_id not in centers:
                continue
            cx, cy = centers[item.storage_id]
            self._circle(cx, cy, item.required_distance_m, COLOR_UVV, f"R_увв = {fmt(item.required_distance_m)} м ({item.object_id})")

    @staticmethod
    def _center(storage: StorageBuilding) -> tuple[float, float]:
        left, bottom, right, top = storage_bounds(storage)
        return (left + right) / 2.0, (bottom + top) / 2.0

    def _circle(self, cx: float, cy: float, radius: float, color: QColor, tooltip: str) -> None:
        if radius <= 0.0:
            return
        item = self._scene.addEllipse(
            QRectF(cx - radius, -cy - radius, 2 * radius, 2 * radius),
            QPen(color, 0.3, Qt.PenStyle.DashLine),
            QBrush(Qt.BrushStyle.NoBrush),
        )
        item.setToolTip(tooltip)
