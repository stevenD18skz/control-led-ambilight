@echo off
setlocal
cd /d "%~dp0"
title Instalar y ejecutar Control LED

set "PYTHON_CMD="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=py -3"

if not defined PYTHON_CMD (
    python --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD goto :python_missing

%PYTHON_CMD% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto :python_old

echo Preparando el entorno virtual...
if not exist ".venv\Scripts\python.exe" (
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 goto :install_error
)

echo Actualizando pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :install_error

echo Instalando dependencias...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :install_error

if not exist ".venv\Scripts\pythonw.exe" goto :install_error

echo Iniciando Control LED...
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0src\main.py"
exit /b 0

:python_missing
echo No se encontro Python. Instala Python 3.10 o superior y vuelve a ejecutar este archivo.
echo Durante la instalacion de Python, activa la opcion para agregarlo al PATH.
pause
exit /b 1

:python_old
echo Se necesita Python 3.10 o superior. Actualiza Python y vuelve a intentarlo.
pause
exit /b 1

:install_error
echo Ocurrio un error al preparar el entorno o instalar las dependencias.
echo Comprueba tu conexion a Internet y vuelve a ejecutar este archivo.
pause
exit /b 1
