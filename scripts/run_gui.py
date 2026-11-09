"""Запуск графического интерфейса из исходников без установки пакета.

Использование: `.\.venv\Scripts\python.exe scripts\run_gui.py [файл_проекта.json]`.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from explosions_core.gui.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
