@echo off
rem Запуск интерфейса без окна консоли. Используется интерпретатор виртуального окружения напрямую (не Activate.ps1).
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Не найдено виртуальное окружение .venv. Создайте его и установите зависимости: pip install -e .[gui]
    pause
    exit /b 1
)
rem pythonw.exe не показывает ошибок: наличие PySide6 проверяется заранее через python.exe.
".venv\Scripts\python.exe" -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo В окружении .venv не установлен PySide6. Установите зависимости интерфейса:
    echo   uv sync --extra gui    или    .venv\Scripts\python.exe -m pip install -e .[gui]
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "scripts\run_gui.py" %*
