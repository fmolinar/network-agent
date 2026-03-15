@echo off
setlocal

set "ROOT_DIR=%~dp0.."
pushd "%ROOT_DIR%" >nul
if "%PYTHONPATH%"=="" (
  set "PYTHONPATH=%ROOT_DIR%\src"
) else (
  set "PYTHONPATH=%ROOT_DIR%\src;%PYTHONPATH%"
)

set "PYTHON_BIN=%ROOT_DIR%\.venv\Scripts\python.exe"
if not exist "%PYTHON_BIN%" (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Error: Python 3 not found.
    popd >nul
    exit /b 1
  )
  set "PYTHON_BIN=python"
)

"%PYTHON_BIN%" "%ROOT_DIR%\gui\chat_app.py"
popd >nul
