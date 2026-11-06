"""Единый реестр ссылок на пункты НПА РК.

Все ссылки (clause) в нарушениях, чертежах и расчетно-пояснительной записке берутся отсюда.
Редакция: текст Приказа МИР РК № 343 по состоянию на 02.10.2025 (Documentation/v1400010244.02-10-2025.rus.pdf).
При смене редакции нормативного акта правка выполняется только в этом модуле.
"""

from typing import Final

ORDER_343: Final = "Приказа МИР РК № 343"
ORDER_343_EDITION: Final = f"{ORDER_343} (ред. от 02.10.2025)"
SP_LIGHTNING: Final = "СП РК 2.04-103-2013"

# Модуль 1: совместимость ВМ (п. 8, Приложение 2; исключения п. 9)
CLAUSE_COMPATIBILITY: Final = f"п. 8 и Приложение 2 {ORDER_343_EDITION}"
CLAUSE_COMPATIBILITY_EXCEPTION: Final = f"п. 9 {ORDER_343_EDITION}"

# Внутренняя планировка хранилищ (п. 579–580)
CLAUSE_STACK: Final = f"п. 579 {ORDER_343_EDITION}"
CLAUSE_RACK: Final = f"п. 580 {ORDER_343_EDITION}"

# Генплан стационарного склада: запретная зона, ограда, расстояния (п. 590, 592, 593)
CLAUSE_FORBIDDEN_ZONE: Final = f"п. 590 (подпункт 5) {ORDER_343_EDITION}"
CLAUSE_FENCE_PERMANENT: Final = f"п. 593 {ORDER_343_EDITION}"
CLAUSE_TARE: Final = f"п. 592 {ORDER_343_EDITION}"
CLAUSE_GUARDHOUSE: Final = f"п. 592 и п. 590 (подпункт 5) {ORDER_343_EDITION}"
CLAUSE_TEMPORARY_FENCE: Final = f"п. 618 {ORDER_343_EDITION}"
CLAUSE_TEMPORARY_AS_PERMANENT: Final = f"п. 618 (в остальном как к постоянным складам) {ORDER_343_EDITION}"
CLAUSE_SHORT_TERM: Final = f"п. 621 {ORDER_343_EDITION}"
CLAUSE_OPEN_FIRE: Final = f"п. 16 {ORDER_343_EDITION}"
CLAUSE_PRP: Final = f"п. 48 {ORDER_343_EDITION}"

# Совместная перевозка ВВ и СИ (п. 74)
CLAUSE_MOBILE_PAYLOAD: Final = f"п. 74 (подпункт 1) {ORDER_343_EDITION}"
CLAUSE_MOBILE_POWDER: Final = f"п. 74 (подпункт 4) {ORDER_343_EDITION}"

# Приложение 11: УВВ (Глава 3, таблица 2, формулы (10), (11)) и передача детонации (Глава 4, формулы (19), таблицы 4, 5)
CLAUSE_UVV: Final = f"п. 573 и п. 10, формулы (10), (11), таблица 2 Приложения 11 {ORDER_343_EDITION}"
CLAUSE_UVV_TABLE_2: Final = f"таблица 2 Приложения 11 {ORDER_343_EDITION}"
CLAUSE_DETONATION: Final = f"п. 15, 17, формула (19), таблица 4 Приложения 11 {ORDER_343_EDITION}"
CLAUSE_DETONATION_TABLE_4: Final = f"таблица 4 Приложения 11 {ORDER_343_EDITION}"
CLAUSE_DETONATION_TABLE_5: Final = f"таблица 5 Приложения 11 {ORDER_343_EDITION}"
CLAUSE_DETONATION_MAX_PASSIVE: Final = f"п. 17 Приложения 11 {ORDER_343_EDITION}"
CLAUSE_DETONATION_SENSITIVE: Final = f"п. 19 Приложения 11 {ORDER_343_EDITION}"
CLAUSE_DETONATION_PLACEMENT: Final = f"п. 16 Приложения 11 {ORDER_343_EDITION}"
CLAUSE_DETONATION_TOTAL_STOCK: Final = f"п. 17 (абзац 3) Приложения 11 {ORDER_343_EDITION}"
CLAUSE_UVV_BERMED: Final = f"п. 10, подпункт 2 (примечание к таблице 2) Приложения 11 {ORDER_343_EDITION}"

# Обвалование (п. 602–605; грунт — п. 603; гребень — п. 604; экран — п. 605)
CLAUSE_BERM: Final = f"п. 602-605 {ORDER_343_EDITION}"
CLAUSE_BERM_SOIL: Final = f"п. 603 {ORDER_343_EDITION}"
CLAUSE_BERM_CREST: Final = f"п. 604 {ORDER_343_EDITION}"
CLAUSE_BERM_SCREEN: Final = f"п. 605 {ORDER_343_EDITION}"

# Молниезащита (СП РК 2.04-103-2013, сверено с PDF в Documentation)
CLAUSE_LIGHTNING_SPHERE: Final = f"п. 7.2 (формулы (2-1), (2-1а)) {SP_LIGHTNING}"
CLAUSE_LIGHTNING_PROTECTION_LEVEL: Final = f"табл. 2 {SP_LIGHTNING} (радиус катящейся сферы по уровню защиты)"
CLAUSE_LIGHTNING_ZONES_RD: Final = "РД 34.21.122-87 «Инструкция по устройству молниезащиты зданий и сооружений» (текст в Documentation отсутствует, зоны А и Б как альтернативный метод)"
SO_153_LIGHTNING: Final = "СО 153-34.21.122-2003 «Инструкция по устройству молниезащиты зданий, сооружений и промышленных коммуникаций»"
CLAUSE_LIGHTNING_SO153: Final = f"п. 3.3.2.1, табл. 3.4, формула (3.1) {SO_153_LIGHTNING}"
CLAUSE_LIGHTNING_SO153_RELIABILITY: Final = f"п. 2.2 {SO_153_LIGHTNING} (специальные объекты: надежность 0,9–0,999)"
CLAUSE_LIGHTNING_REQUIRED: Final = f"п. 691 и п. 693 {ORDER_343_EDITION}"
CLAUSE_ARRESTER_CLEARANCE: Final = f"5 м от опоры молниеотвода до стен хранилища по заданию № 4 (в {SP_LIGHTNING} отсутствует; п. 9.3 отсылает к ПУЭ, табл. 15)"

# Таблица 3 Приложения 11 (допустимые расстояния до объектов по УВВ, п. 10, подпункт 7)
CLAUSE_UVV_TABLE_3: Final = f"таблица 3 Приложения 11 (п. 10, подпункт 7) {ORDER_343_EDITION}"

# Классификация ВМ по ТР ТС 028/2012 (Приложение 3: шифры по группам совместимости)
CLAUSE_TR_TS_CLASSIFICATION: Final = "Приложение 3 ТР ТС 028/2012 (шифры подклассов по группам совместимости)"

# Раздел 1 расчетно-пояснительной записки: перечень НПА с реквизитами
NPA_LIST: Final[tuple[str, ...]] = (
    "Приказ Министра по инвестициям и развитию РК от 30.12.2014 № 343 «Об утверждении Правил обеспечения "
    "промышленной безопасности для опасных производственных объектов, ведущих взрывные работы и работы со "
    "взрывчатыми материалами промышленного назначения» (в ред. Приказа МИР РК от 22.12.2017 № 895 и Приказа "
    "МЧС РК от 17.03.2023 № 120; текст по состоянию на 02.10.2025);",
    "Технический регламент Таможенного союза ТР ТС 028/2012 «О безопасности взрывчатых веществ и изделий на "
    "их основе» (Приложение № 3);",
    "Приказ МИР РК от 30.12.2014 № 359 «Об утверждении Правил выдачи разрешений на производство взрывных работ» "
    "(в ред. Приказа МЧС РК от 13.04.2026 № 157) — текст в исходных материалах отсутствует, в расчетах не применяется;",
    "СП РК 2.04-103-2013 «Устройство молниезащиты зданий и сооружений» (СН РК 2.04-02-2011);",
    f"{SO_153_LIGHTNING} (Приказ Минэнерго России от 30.06.2003 № 280) — формулы зон одиночного стержневого "
    "молниеотвода, применяется как альтернативный метод;",
    "Приказ МЧС РК от 21.02.2022 № 55 «Об утверждении Правил пожарной безопасности» — специальных расчетных норм "
    "для складов ВМ не содержит.",
)
