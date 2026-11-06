# explosions-core

Инженерное расчетное ядро проектирования стационарных и передвижных складов взрывчатых материалов (ВМ)
для карьеров по нормам Республики Казахстан (Приказ МИР РК № 343, текст по состоянию на 02.10.2025,
ТР ТС 028/2012, СП РК 2.04-103-2013, СО 153-34.21.122-2003).

## Структура

```
src/explosions_core/
  norms/        константы Приказа № 343, реестр ссылок на НПА, реестр источников констант (sources.py),
                таблицы 2, 3, 4, 5 Приложения 11 (data/*.json)
  domain/       модели Pydantic v2 (импорт: from explosions_core.domain import ...)
  validators/   проверки совместимости, планировки, периметра, ПРП, складов
  calc/         габариты хранилищ, r_д и R_увв, обвалование, молниезащита, геометрия
  pipeline.py   единый конвейер calculate_project(ProjectDefinition) -> ProjectCalculationResult
  io/           чтение и запись файла проекта .json (utf-8)
  export/cad/   DXF-чертежи (ezdxf, R2010) для nanoCAD
  export/reports/  расчетно-пояснительная записка DOCX (python-docx)
  export/project_export.py  выгрузка всех выходных файлов расчета
  cli.py        командная строка (python -m explosions_core)
examples/       демонстрационный файл проекта demo_project.json
scripts/        генерация эталонных DXF, DOCX и demo_project.json
tests/          тесты pytest, эталонные данные в tests/fixtures/
Documentation/  тексты НПА (PDF)
docs/           сверка с НПА (norms_verification.md) и реестр допущений (assumptions.md)
```

## Файл проекта

Файл проекта — JSON в кодировке utf-8 с полями `schema_version`, `project` (модель `WarehouseProjectInput`),
`storage_designs` (проектные данные по `storage_id`: раздел `sizing`, высоты, обвалование, молниезащита)
и `settings` (параметры расчета). Неизвестные поля отвергаются с указанием пути к ошибке,
чтобы опечатка не терялась молча. Пример: `examples\demo_project.json`.

Молниезащита (`storage_designs[].lightning`): `method` — `rolling_sphere_sp_rk` (по умолчанию, катящаяся сфера
СП РК, `protection_level` I/II/III), `single_rod_so_153` (табл. 3.4 СО 153, `reliability` 0.9/0.99/0.999)
или `zones_rd_34_21_122` (зоны А/Б, нужен `zone_type`; файлы с одним `zone_type` считаются так же, как раньше).
УВВ по таблице 3 Приложения 11: `settings.uvv_method = "table_3"` и `table3_object_category` (1–3) у каждого
внешнего объекта.

## Установка (Windows, без Activate.ps1)

```
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .[dev]
```

При ошибке корпоративного SSL-сертификата добавьте `--use-feature=truststore`.

## Запуск

```
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts\generate_sample_dxf.py
.\.venv\Scripts\python.exe scripts\generate_sample_report.py
```

Команда расчета проекта из файла (из корня проекта; `src` добавляется в путь интерпретатора):

```
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m explosions_core validate examples\demo_project.json
.\.venv\Scripts\python.exe -m explosions_core calc examples\demo_project.json --dxf --docx --json --out output_project
```

Коды выхода `calc`: 0 — нарушений и ошибок расчета нет; 1 — ошибка входных данных или файла;
2 — расчет выполнен, но есть нарушения нормативов или ошибки модулей.

Чертежи сохраняются в `output_dxf\`, записка — в `output_reports\` (обе папки не хранятся в Git).

## Графический интерфейс

Интерфейс на PySide6 — нативное окно Windows без веб-фреймворков и сетевых портов. Установка
зависимости: `.\.venv\Scripts\python.exe -m pip install --use-feature=truststore PySide6-Essentials`.

Запуск: двойной щелчок по `run_gui.cmd` или `.\.venv\Scripts\python.exe scripts\run_gui.py [файл_проекта.json]`.

Разделы окна: «Проект» (общие данные, периметр, ПРП, передвижной склад, настройки расчета),
«Хранилища» (список слева; вкладки «Общие и ВМ» и «Проектирование»), «Внешние объекты»,
«Результаты» (баннер статуса и таблицы нарушений, замечаний, r_д, R_увв, габаритов, обвалования,
молниезащиты; нарушения выделены красным), «План» (генплан с окружностями безопасных расстояний).
Кнопка «Рассчитать» — F5, «Выгрузить» — Ctrl+E (DXF, DOCX и JSON в выбранную папку).

## Ограничения

Нормы Приказа № 343 и Приложения 11 сверены с PDF в `Documentation` (см. `docs\norms_verification.md`),
эталонные тесты воспроизводят примеры п. 21 Приложения 11 и таблицы 3 и 5. Молниезащита сверена с
СП РК 2.04-103-2013 и СО 153-34.21.122-2003; текстов РД 34.21.122-87 и ПУЭ в проекте нет. Решения, которых нет в
тексте НПА, перечислены в `docs\assumptions.md` и требуют подтверждения инженером.
