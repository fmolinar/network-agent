@echo off
setlocal enabledelayedexpansion

set "MODEL=%~1"
if "%MODEL%"=="" set "MODEL=llama3.1"
if "%OLLAMA_HOST%"=="" set "OLLAMA_HOST=127.0.0.1:11434"

where ollama >nul 2>nul
if errorlevel 1 (
  echo Error: 'ollama' is not installed. Download it from https://ollama.com/download
  exit /b 1
)

echo Starting Ollama on %OLLAMA_HOST%
tasklist /FI "IMAGENAME eq ollama.exe" | find /I "ollama.exe" >nul
if errorlevel 1 (
  start "" /B ollama serve > "%TEMP%\ollama-serve.log" 2>&1
  timeout /T 2 /NOBREAK >nul
)

echo Pulling model: %MODEL%
ollama pull %MODEL%
if errorlevel 1 exit /b 1

echo LLM ready
echo Provider: ollama
echo Model: %MODEL%
echo Endpoint: http://%OLLAMA_HOST%/api/chat
