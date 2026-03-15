@echo off
setlocal enabledelayedexpansion

set "ROOT_DIR=%~dp0.."
pushd "%ROOT_DIR%" >nul

if "%NETWORK_AGENT_LOCAL_MODEL%"=="" (
  set "MODEL=llama3.1"
) else (
  set "MODEL=%NETWORK_AGENT_LOCAL_MODEL%"
)

if "%OLLAMA_HOST%"=="" set "OLLAMA_HOST=127.0.0.1:11434"

set "PYTHON_BIN=%ROOT_DIR%\.venv\Scripts\python.exe"
if not exist "%PYTHON_BIN%" (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Error: Python not found. Install Python 3.10+ to run network-agent.
    popd >nul
    exit /b 1
  )
  set "PYTHON_BIN=python"
)

set "USE_LLM_AGENTS=0"
where ollama >nul 2>nul
if not errorlevel 1 (
  echo Local LLM runtime detected ^(ollama^).
  call "%ROOT_DIR%\llm\spin_llm.bat" "%MODEL%"
  if not errorlevel 1 (
    set "USE_LLM_AGENTS=1"
  ) else (
    echo Could not start local LLM cleanly. Program will run manually.
  )
) else (
  echo Ollama is not installed or unavailable. Program will run manually.
)

echo.
echo Network Agent Chat CLI
echo Type your network issue and press Enter.
echo Type 'exit' or 'quit' to stop.
echo.

:loop
set "USER_ISSUE="
set /p "USER_ISSUE=You> "
if /I "%USER_ISSUE%"=="exit" goto done
if /I "%USER_ISSUE%"=="quit" goto done
if "%USER_ISSUE%"=="" goto loop

set "CMD=%PYTHON_BIN% -m network_agent.cli --prompt "%USER_ISSUE%" --host-os auto --collect-live-stats"
if "%USE_LLM_AGENTS%"=="1" (
  set "CMD=%CMD% --enable-llm-agents --agent-llm-provider ollama --agent-llm-model %MODEL% --agent-llm-base-url http://%OLLAMA_HOST%/api/chat"
)

for /f "delims=" %%I in ('%CMD% 2^> "%TEMP%\network-agent-chat.err"') do set "RAW_JSON=!RAW_JSON!%%I"
if errorlevel 1 (
  echo Agent^> Execution failed. Check %TEMP%\network-agent-chat.err
  set "RAW_JSON="
  echo.
  goto loop
)

echo Agent^>
echo(!RAW_JSON! | "%PYTHON_BIN%" -c "import json,sys; p=json.load(sys.stdin); d=p.get('diagnosis',{}); v=p.get('validation',{}); c=d.get('candidate_causes_ranked',[]); t=c[0] if c else {}; print(f""Summary: {d.get('problem_summary','n/a')}""); print(f""Top cause: {t.get('title','n/a')}""); print(f""Confidence: {d.get('confidence_score','n/a')}""); r=d.get('remediation_plan',[]); [print(f'- {s}') for s in r[:3]] if r else None; n=v.get('reasons',[]); [print(f'- {x}') for x in n] if n else None"
set "RAW_JSON="
echo.
goto loop

:done
echo Exiting.
popd >nul
