"""Общие геометрические хелперы для хранилищ ВМ на генплане."""

import math

from explosions_core.domain import StorageBuilding

Bounds = tuple[float, float, float, float]


def storage_key(storage: StorageBuilding) -> str:
    return storage.storage_id if storage.storage_id is not None else storage.name


def storage_bounds(storage: StorageBuilding) -> Bounds:
    if storage.x_m is None or storage.y_m is None or storage.length_m is None or storage.width_m is None:
        raise ValueError(f"Для хранилища '{storage_key(storage)}' не заданы координаты и размеры на генплане")
    return (storage.x_m, storage.y_m, storage.x_m + storage.length_m, storage.y_m + storage.width_m)


def storage_center(storage: StorageBuilding) -> tuple[float, float]:
    x1, y1, x2, y2 = storage_bounds(storage)
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def nearest_point(storage: StorageBuilding, other: StorageBuilding) -> tuple[float, float]:
    x1, y1, x2, y2 = storage_bounds(storage)
    ox, oy = storage_center(other)
    return (min(max(ox, x1), x2), min(max(oy, y1), y2))


def clear_distance_between(storage_i: StorageBuilding, storage_j: StorageBuilding) -> float:
    i_x1, i_y1, i_x2, i_y2 = storage_bounds(storage_i)
    j_x1, j_y1, j_x2, j_y2 = storage_bounds(storage_j)
    gap_x = max(j_x1 - i_x2, i_x1 - j_x2, 0.0)
    gap_y = max(j_y1 - i_y2, i_y1 - j_y2, 0.0)
    return math.hypot(gap_x, gap_y)


def storages_bounds(storages: list[StorageBuilding]) -> Bounds:
    boxes = [storage_bounds(item) for item in storages]
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def offset_bounds(bounds: Bounds, offset: float) -> Bounds:
    x1, y1, x2, y2 = bounds
    return (x1 - offset, y1 - offset, x2 + offset, y2 + offset)
