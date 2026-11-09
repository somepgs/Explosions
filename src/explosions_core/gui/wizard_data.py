"""Общие данные мастера: один словарь проекта, который правят все шаги (без Qt).

Каждый шаг при показе читает свои поля отсюда и при изменении записывает только свои поля.
Поэтому одно хранилище можно редактировать на шагах 2–5, и данные других шагов не теряются.
Разделы проектирования (`storage_designs`) привязаны к обозначению хранилища и переносятся при его смене.
"""

import copy
from typing import Any

from explosions_core.domain import ProjectDefinition, WarehouseDuration
from explosions_core.gui.session import definition_from_dict


def storage_key_of(storage: dict[str, Any]) -> str:
    """Ключ хранилища, как в конвейере: обозначение, а если его нет — название."""
    return storage.get("storage_id") or storage.get("name") or ""


def storage_title(storage: dict[str, Any]) -> str:
    name = storage.get("name") or "Без имени"
    key = storage.get("storage_id")
    return f"{name} ({key})" if key else name


def _has_values(design: dict[str, Any]) -> bool:
    return any(value is not None for name, value in design.items() if name != "storage_id")


class WizardData:
    """Редактируемая копия определения проекта в виде словарей."""

    def __init__(self, definition: ProjectDefinition | None = None) -> None:
        self.schema_version = "1"
        self.project: dict[str, Any] = {}
        self.settings: dict[str, Any] = {}
        self.storages: list[dict[str, Any]] = []
        self.designs: dict[str, dict[str, Any]] = {}
        self.targets: list[dict[str, Any]] = []
        self.selected_storage = 0
        self._loaded_designs: set[str] = set()
        if definition is not None:
            self.load(definition)

    # ---------- загрузка и сборка ----------

    def load(self, definition: ProjectDefinition) -> None:
        data = definition.model_dump(mode="json")
        project = dict(data["project"])
        self.schema_version = data["schema_version"]
        self.storages = [dict(s) for s in project.pop("storages", [])]
        self.targets = [dict(t) for t in project.pop("external_targets", [])]
        self.project = project
        self.settings = dict(data.get("settings") or {})
        self.designs = {d["storage_id"]: dict(d) for d in data.get("storage_designs", []) if d.get("storage_id")}
        self._loaded_designs = set(self.designs)
        self.selected_storage = 0

    def to_dict(self) -> dict[str, Any]:
        project = dict(self.project)
        project["storages"] = [dict(s) for s in self.storages]
        project["external_targets"] = [dict(t) for t in self.targets]
        return {
            "schema_version": self.schema_version,
            "project": project,
            "storage_designs": self.designs_list(),
            "settings": dict(self.settings),
        }

    def definition(self) -> ProjectDefinition:
        """Проверка схемой проекта; ошибка — `ProjectSessionError` с русским текстом."""
        return definition_from_dict(self.to_dict())

    def designs_list(self) -> list[dict[str, Any]]:
        """Разделы проектирования в порядке хранилищ. Пустые новые разделы не выгружаются."""
        result = []
        for storage in self.storages:
            key = storage_key_of(storage)
            design = self.designs.get(key)
            if design is None:
                continue
            if _has_values(design) or key in self._loaded_designs:
                item = dict(design)
                item["storage_id"] = key
                result.append(item)
        return result

    # ---------- хранилища ----------

    def storage_count(self) -> int:
        return len(self.storages)

    def storage(self, index: int) -> dict[str, Any]:
        return self.storages[index]

    def key(self, index: int) -> str:
        return storage_key_of(self.storages[index])

    def update_storage(self, index: int, values: dict[str, Any]) -> None:
        """Записывает поля хранилища. При смене обозначения раздел проектирования переходит к новому ключу."""
        old_key = storage_key_of(self.storages[index])
        self.storages[index].update(values)
        new_key = storage_key_of(self.storages[index])
        if new_key != old_key and old_key in self.designs and new_key not in self.designs:
            design = self.designs.pop(old_key)
            design["storage_id"] = new_key
            self.designs[new_key] = design
            if old_key in self._loaded_designs:
                self._loaded_designs.discard(old_key)
                self._loaded_designs.add(new_key)

    def design(self, index: int) -> dict[str, Any] | None:
        return self.designs.get(self.key(index))

    def update_design(self, index: int, values: dict[str, Any]) -> None:
        key = self.key(index)
        design = dict(self.designs.get(key) or {"storage_id": key})
        design.update(values)
        design["storage_id"] = key
        self.designs[key] = design

    def _next_id(self) -> str:
        existing = {s.get("storage_id") for s in self.storages} | set(self.designs)
        index = len(self.storages) + 1
        while f"S{index}" in existing:
            index += 1
        return f"S{index}"

    def add_storage(self) -> int:
        template = dict(self.storages[-1]) if self.storages else {}
        storage = {
            "name": f"Хранилище {len(self.storages) + 1}",
            "storage_id": self._next_id(),
        }
        for name in ("category", "duration", "location_type"):
            if name in template:
                storage[name] = template[name]
        self.storages.append(storage)
        self.selected_storage = len(self.storages) - 1
        return self.selected_storage

    def copy_storage(self, index: int) -> int:
        source = copy.deepcopy(self.storages[index])
        source_design = self.designs.get(storage_key_of(source))
        source["storage_id"] = self._next_id()
        source["name"] = f"{source.get('name') or 'Хранилище'} (копия)"
        self.storages.append(source)
        if source_design is not None:
            design = copy.deepcopy(source_design)
            design["storage_id"] = source["storage_id"]
            self.designs[source["storage_id"]] = design
        self.selected_storage = len(self.storages) - 1
        return self.selected_storage

    def remove_storage(self, index: int) -> int:
        key = storage_key_of(self.storages[index])
        self.storages.pop(index)
        if all(storage_key_of(s) != key for s in self.storages):
            self.designs.pop(key, None)
            self._loaded_designs.discard(key)
        self.selected_storage = min(index, len(self.storages) - 1) if self.storages else 0
        return self.selected_storage

    # ---------- тип склада для всех хранилищ ----------

    def common_duration(self) -> str | None:
        """Тип склада, если он одинаков у всех хранилищ; иначе None."""
        values = {s.get("duration") for s in self.storages}
        if len(values) == 1:
            value = values.pop()
            return getattr(value, "value", value)
        return None

    def set_duration_for_all(self, duration: WarehouseDuration | str) -> None:
        raw = getattr(duration, "value", duration)
        for storage in self.storages:
            storage["duration"] = raw
