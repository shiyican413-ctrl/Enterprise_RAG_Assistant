@echo off
setlocal EnableExtensions
set "BACKEND_EXIT_CODE=0"

set "BACKEND_PORT=%~1"
if "%BACKEND_PORT%"=="" set "BACKEND_PORT=8000"

cd /d "%~dp0.."
set "PYTHONPATH=%CD%"
set "PYTHONUTF8=1"

if not exist ".venv\Scripts\python.exe" (
  echo [backend] Python virtual environment was not found. Run start.bat first.
  set "BACKEND_EXIT_CODE=1"
  goto failed
)

".venv\Scripts\python.exe" -m uvicorn backend.ai_service.main:app --reload --host 127.0.0.1 --port "%BACKEND_PORT%"
set "BACKEND_EXIT_CODE=%ERRORLEVEL%"

if not "%BACKEND_EXIT_CODE%"=="0" goto failed

goto end

:failed
echo.
echo [backend] Uvicorn exited with code %BACKEND_EXIT_CODE%.
echo [backend] Review the traceback above. This window will stay open when launched from start.bat.

:end
endlocal & exit /b %BACKEND_EXIT_CODE%
