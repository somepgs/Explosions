@echo off
rem Запуск интерфейса без окна консоли. Используется интерпретатор виртуального окружения напрямую (не Activate.ps1).
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Не найдено виртуальное окружение .venv. Создайте его и установите зависимости: pip install -e .[gui]
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "scripts\run_gui.py" %*
