"""Проверка готовности данных перед расчетом: что не заполнено, где и что сделать (без Qt)."""

from dataclasses import dataclass
from typing import Literal

from explosions_core.domain import (
    ProjectDefinition,
    StorageBuilding,
    StorageDesignInput,
    WarehouseDuration,
    WarehouseProjectInput,
)

ReadinessLevel = Literal["error", "warning", "info"]

STEP_PROJECT = 1
STEP_STORAGES = 2
STEP_SIZING = 3
STEP_PLACEMENT = 4
STEP_LIGHTNING = 5
STEP_TERRITORY = 6
STEP_TARGETS = 7
STEP_CALCULATION = 8
STEP_BERM = STEP_PLACEMENT
MASS_MISMATCH_TOLERANCE_KG = 0.5


@dataclass(frozen=True)
class ReadinessItem:
    level: ReadinessLevel
    step: int
    storage: str | None
    message: str
    hint: str


def storage_key(storage: StorageBuilding) -> str:
    return storage.storage_id or storage.name


def _design_for(definition: ProjectDefinition, key: str) -> StorageDesignInput | None:
    for design in definition.storage_designs:
        if design.storage_id == key:
            return design
    return None


def check_readiness(definition: ProjectDefinition) -> list[ReadinessItem]:
    """Список замечаний. Уровень error — расчет не выполнится или результат неполон; warning — расчет пойдет, но проверка неполна."""
    items: list[ReadinessItem] = []
    project = definition.project
    storages = project.storages

    if not project.name.strip():
        items.append(
            ReadinessItem("error", STEP_PROJECT, None, "Не указано название склада", "Заполните название на шаге «Проект».")
        )
    if not storages:
        items.append(
            ReadinessItem(
                "error",
                STEP_STORAGES,
                None,
                "В проекте нет ни одного хранилища",
                "Добавьте хранилище на шаге «Хранилища и ВМ».",
            )
        )

    keys = [storage_key(storage) for storage in storages]
    for key in sorted({k for k in keys if keys.count(k) > 1}):
        items.append(
            ReadinessItem(
                "error",
                STEP_STORAGES,
                key,
                f"Два хранилища с одинаковым обозначением «{key}»",
                "Задайте разные обозначения хранилищ на шаге «Хранилища и ВМ».",
            )
        )

    for storage, key in zip(storages, keys):
        _check_storage(items, definition, storage, key)

    _check_territory(items, project)
    _check_targets(items, project)
    _check_detonation_coordinates(items, storages, keys)
    return items


def _check_storage(
    items: list[ReadinessItem],
    definition: ProjectDefinition,
    storage: StorageBuilding,
    key: str,
) -> None:
    if not storage.items:
        items.append(
            ReadinessItem(
                "error",
                STEP_STORAGES,
                key,
                "В хранилище не указаны взрывчатые материалы",
                "Добавьте хотя бы один вид ВМ во вкладке «ВМ».",
            )
        )
    for item in storage.items:
        if item.mass_kg <= 0:
            items.append(
                ReadinessItem(
                    "error",
                    STEP_STORAGES,
                    key,
                    f"У ВМ «{item.name}» не указана масса нетто",
                    "Укажите массу нетто во вкладке «ВМ».",
                )
            )
        if item.detonation_class is None:
            items.append(
                ReadinessItem(
                    "warning",
                    STEP_STORAGES,
                    key,
                    f"У ВМ «{item.name}» не выбран класс по таблице 4 Приложения 11",
                    "Выберите класс ВМ во вкладке «ВМ»; без него передача детонации не рассчитается.",
                )
            )
    if storage.duration in (WarehouseDuration.PERMANENT, WarehouseDuration.TEMPORARY):
        design = _design_for(definition, key)
        if design is None or design.lightning is None:
            items.append(
                ReadinessItem(
                    "warning",
                    STEP_LIGHTNING,
                    key,
                    "Постоянное или временное хранилище без раздела молниезащиты (п. 691 Приказа № 343)",
                    "Добавьте молниеотвод на шаге «Молниезащита».",
                )
            )
    _check_building_size(items, definition, storage, key)
    _check_berm(items, definition, storage, key)


def _check_building_size(
    items: list[ReadinessItem],
    definition: ProjectDefinition,
    storage: StorageBuilding,
    key: str,
) -> None:
    design = _design_for(definition, key)
    if design is None or design.sizing is None:
        items.append(
            ReadinessItem(
                "warning",
                STEP_SIZING,
                key,
                "Не рассчитаны габариты хранилища (нет раздела «Габариты»)",
                "Заполните шаг «Планировка и габариты»: без него не будут известны размеры здания и высота груза.",
            )
        )
    if storage.length_m is None or storage.width_m is None:
        items.append(
            ReadinessItem(
                "info",
                STEP_PLACEMENT,
                key,
                "Размеры здания не заданы, будут взяты из расчета габаритов",
                "При необходимости задайте длину и ширину здания на шаге «Размещение и обвалование».",
            )
        )
    if design is not None and design.sizing is not None:
        declared = design.sizing.total_net_explosive_mass_kg
        listed = sum(item.mass_kg for item in storage.items)
        if storage.items and abs(declared - listed) > MASS_MISMATCH_TOLERANCE_KG:
            items.append(
                ReadinessItem(
                    "warning",
                    STEP_SIZING,
                    key,
                    f"Проектная масса в габаритах ({declared:g} кг) не равна сумме партий ВМ ({listed:g} кг)",
                    "Сведите массу на шаге «Хранилища и ВМ» и в разделе «Планировка и габариты».",
                )
            )


def _check_berm(
    items: list[ReadinessItem],
    definition: ProjectDefinition,
    storage: StorageBuilding,
    key: str,
) -> None:
    design = _design_for(definition, key)
    has_berm_data = design is not None and design.berm is not None
    if has_berm_data and not storage.is_bermed:
        items.append(
            ReadinessItem(
                "warning",
                STEP_PLACEMENT,
                key,
                "Заполнен раздел обвалования, но хранилище не отмечено как обвалованное",
                "Отметьте «Обвалованное хранилище» на шаге «Хранилища и ВМ» или удалите раздел обвалования.",
            )
        )
    if storage.is_bermed and not has_berm_data:
        items.append(
            ReadinessItem(
                "warning",
                STEP_PLACEMENT,
                key,
                "Хранилище отмечено как обвалованное, но параметры вала не заданы",
                "Заполните параметры вала на шаге «Размещение и обвалование» (грунт, гребень, откос).",
            )
        )
    if has_berm_data and design.load_top_height_m is None and design.sizing is None:
        items.append(
            ReadinessItem(
                "error",
                STEP_PLACEMENT,
                key,
                "Для вала не известна высота верха груза (п. 604 Приказа № 343)",
                "Заполните шаг «Планировка и габариты» или укажите высоту верха груза на шаге «Размещение и обвалование».",
            )
        )
    if design is not None and design.eaves_height_m is None and design.berm is not None:
        items.append(
            ReadinessItem(
                "warning",
                STEP_PLACEMENT,
                key,
                "Не задана высота карниза для расчета вала",
                "Укажите высоту карниза на шаге «Размещение и обвалование» или «Молниезащита».",
            )
        )


def _check_territory(items: list[ReadinessItem], project: WarehouseProjectInput) -> None:
    if project.fence_height_m is None or project.fence_to_nearest_storage_m is None:
        items.append(
            ReadinessItem(
                "warning",
                STEP_TERRITORY,
                None,
                "Не заполнены параметры ограды склада (высота, расстояние до хранилища)",
                "Заполните шаг «Территория»: без этого не проверяется генплан (п. 590, 593).",
            )
        )
    if project.forbidden_zone_width_m is None:
        items.append(
            ReadinessItem(
                "warning",
                STEP_TERRITORY,
                None,
                "Не задана ширина запретной зоны",
                "Укажите ширину запретной зоны на шаге «Территория».",
            )
        )
    if project.open_fire_ban_radius_m is None:
        items.append(
            ReadinessItem(
                "warning",
                STEP_TERRITORY,
                None,
                "Не задана зона запрета открытого огня",
                "Укажите радиус зоны запрета огня на шаге «Территория» (п. 16 Приказа № 343).",
            )
        )


def _check_targets(items: list[ReadinessItem], project: WarehouseProjectInput) -> None:
    if not project.external_targets:
        items.append(
            ReadinessItem(
                "info",
                STEP_TARGETS,
                None,
                "Внешние охраняемые объекты не добавлены",
                "Добавьте дороги, ЛЭП и здания на шаге «Внешние объекты», если они есть рядом со складом.",
            )
        )


def _check_detonation_coordinates(
    items: list[ReadinessItem],
    storages: list[StorageBuilding],
    keys: list[str],
) -> None:
    missing = [key for storage, key in zip(storages, keys) if storage.x_m is None or storage.y_m is None]
    if len(storages) > 1 and missing:
        items.append(
            ReadinessItem(
                "warning",
                STEP_PLACEMENT,
                ", ".join(missing),
                "У части хранилищ не заданы координаты на генплане: расстояния между ними не проверяются",
                "Укажите координаты X и Y на шаге «Размещение и обвалование» у каждого хранилища (п. 15 Приложения 11).",
            )
        )


def step_statuses(items: list[ReadinessItem]) -> dict[int, ReadinessLevel | None]:
    """Для каждого шага худший уровень замечания: error, warning, info или None (замечаний нет)."""
    rank = {"error": 3, "warning": 2, "info": 1}
    statuses: dict[int, ReadinessLevel | None] = {step: None for step in range(STEP_PROJECT, STEP_CALCULATION + 1)}
    for item in items:
        current = statuses.get(item.step)
        if current is None or rank[item.level] > rank[current]:
            statuses[item.step] = item.level
    return statuses


def readiness_summary(items: list[ReadinessItem]) -> tuple[int, int]:
    """Число ошибок и предупреждений (информационные замечания не считаются)."""
    errors = sum(1 for item in items if item.level == "error")
    warnings = sum(1 for item in items if item.level == "warning")
    return errors, warnings


def has_blocking_errors(items: list[ReadinessItem]) -> bool:
    return any(item.level == "error" for item in items)
