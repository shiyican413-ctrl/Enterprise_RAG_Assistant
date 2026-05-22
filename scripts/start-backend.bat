@echo off
setlocal

set "BACKEND_PORT=%~1"
if "%BACKEND_PORT%"=="" set "BACKEND_PORT=8000"

cd /d "%~dp0.."
set "PYTHONPATH=%CD%"

".venv\Scripts\python.exe" -m uvicorn backend.ai_service.main:app --reload --host 127.0.0.1 --port %BACKEND_PORT%

endlocal
