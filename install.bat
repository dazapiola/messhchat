@echo off
echo.
echo  MeshChat - Instalacion para Windows
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python no encontrado. Instalalo desde https://python.org
    pause
    exit /b 1
)

echo Creando entorno virtual...
python -m venv .venv

echo Instalando dependencias...
.venv\Scripts\pip install --upgrade pip -q
.venv\Scripts\pip install -r requirements.txt -q

echo.
echo  Instalacion completa.
echo  Para iniciar MeshChat ejecuta:
echo.
echo    .venv\Scripts\python meshchat_tui.py
echo.
pause
