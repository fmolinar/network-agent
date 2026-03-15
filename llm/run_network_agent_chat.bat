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
  where py >nul 2>nul
  if errorlevel 1 (
    echo Error: Python launcher 'py' not found. Install Python 3.10+ to run network-agent.
    popd >nul
    exit /b 1
  )
  set "PYTHON_BIN=py"
)

"%PYTHON_BIN%" "%ROOT_DIR%\llm\run_network_agent_chat.py"
popd >nul
