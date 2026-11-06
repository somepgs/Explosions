# explosions-core

Инженерное расчетное ядро проектирования стационарных и передвижных складов взрывчатых материалов (ВМ)
для карьеров по нормам Республики Казахстан (Приказ МИР РК № 343 в ред. Приказов № 895 и МЧС РК № 120,
ТР ТС 028/2012, СП РК 2.04-103-2013).

## Структура

```
src/explosions_core/
  norms/        константы Приказа № 343, реестр ссылок на НПА, таблицы Приложения 11 (data/*.json)
  domain/       модели Pydantic v2 (импорт: from explosions_core.domain import ...)
  validators/   проверки совместимости, планировки, периметра, ПРП, складов
  calc/         габариты хранилищ, r_д и R_увв, обвалование, молниезащита, геометрия
  export/cad/   DXF-чертежи (ezdxf, R2010) для nanoCAD
  export/reports/  расчетно-пояснительная записка DOCX (python-docx)
scripts/        генерация эталонных DXF и DOCX
tests/          тесты pytest, эталонные данные в tests/fixtures/
Documentation/  тексты НПА (PDF)
```

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

Чертежи сохраняются в `output_dxf\`, записка — в `output_reports\` (обе папки не хранятся в Git).

## Ограничения

Значения, не подтвержденные текстом НПА (параметры из технических заданий, табличные сетки Приложения 11),
помечены в коде; до сверки с официальным текстом результаты требуют проверки инженером.
