@echo off
setlocal EnableExtensions
set "STARTUP_EXIT_CODE=0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"

cd /d "%~dp0.."

if not "%~1"=="" set "BACKEND_PORT=%~1"
if not "%~2"=="" set "FRONTEND_PORT=%~2"

if not defined BACKEND_PORT set "BACKEND_PORT=8000"
if not defined FRONTEND_PORT set "FRONTEND_PORT=3001"
set "APP_HOST=127.0.0.1"

echo ============================================
echo   Enterprise RAG Assistant
echo ============================================
echo [start] Project:  %CD%
echo [start] Backend:  http://%APP_HOST%:%BACKEND_PORT%
echo [start] Frontend: http://%APP_HOST%:%FRONTEND_PORT%
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [start] Python was not found. Install Python 3.12+ or add it to PATH.
  set "STARTUP_EXIT_CODE=1"
  goto failed
)

where node >nul 2>&1
if errorlevel 1 (
  echo [start] Node.js was not found. Install Node.js 18+ or add it to PATH.
  set "STARTUP_EXIT_CODE=1"
  goto failed
)

where npm.cmd >nul 2>&1
if errorlevel 1 (
  echo [start] npm was not found. Install Node.js/npm or add it to PATH.
  set "STARTUP_EXIT_CODE=1"
  goto failed
)

if not exist ".env" (
  echo [start] Warning: .env was not found. Model and database features may fail.
)

if not exist ".venv\Scripts\python.exe" (
  echo [start] Creating Python virtual environment...
  python -m venv .venv
  if errorlevel 1 (
    set "STARTUP_EXIT_CODE=%ERRORLEVEL%"
    goto failed
  )
)

echo [start] Installing backend dependencies...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  set "STARTUP_EXIT_CODE=%ERRORLEVEL%"
  goto failed
)

if not exist "frontend\next-web\node_modules" (
  echo [start] Installing frontend dependencies...
  pushd "frontend\next-web" || (
    set "STARTUP_EXIT_CODE=1"
    goto failed
  )
  call npm.cmd install
  if errorlevel 1 (
    set "STARTUP_EXIT_CODE=%ERRORLEVEL%"
    popd
    goto failed
  )
  popd
) else (
  echo [start] Frontend dependencies already exist. Skipping npm install.
)

set "STARTED_SERVICE=0"

set "CHECK_PORT=%BACKEND_PORT%"
call :port_listening
if errorlevel 1 (
  echo [start] Starting backend on http://%APP_HOST%:%BACKEND_PORT%
  start "Enterprise RAG Backend" cmd /k call "%~dp0start-backend.bat" "%BACKEND_PORT%"
  set "STARTED_SERVICE=1"
) else (
  echo [start] Backend port %BACKEND_PORT% is already in use. Reusing existing service.
)

set "CHECK_PORT=%FRONTEND_PORT%"
call :port_listening
if errorlevel 1 (
  echo [start] Starting frontend on http://%APP_HOST%:%FRONTEND_PORT%
  start "Enterprise RAG Frontend" cmd /k call "%~dp0start-frontend.bat" "%BACKEND_PORT%" "%FRONTEND_PORT%"
  set "STARTED_SERVICE=1"
) else (
  echo [start] Frontend port %FRONTEND_PORT% is already in use. Reusing existing service.
)

if "%STARTED_SERVICE%"=="1" (
  echo.
  echo [start] Waiting for services...
  timeout /t 8 /nobreak >nul
)

curl.exe -fsS "http://%APP_HOST%:%BACKEND_PORT%/health" >nul 2>&1
if errorlevel 1 (
  echo [start] Error: backend health check failed.
  echo [start] Check the "Enterprise RAG Backend" window for the traceback.
  set "STARTUP_EXIT_CODE=1"
  goto failed
) else (
  echo [start] Backend health check passed.
)

curl.exe -fsS "http://%APP_HOST%:%FRONTEND_PORT%" >nul 2>&1
if errorlevel 1 (
  echo [start] Error: frontend check failed.
  echo [start] Check the "Enterprise RAG Frontend" window for the error.
  set "STARTUP_EXIT_CODE=1"
  goto failed
) else (
  echo [start] Frontend check passed.
)

echo.
echo Backend:  http://%APP_HOST%:%BACKEND_PORT%
echo API docs: http://%APP_HOST%:%BACKEND_PORT%/docs
echo Frontend: http://%APP_HOST%:%FRONTEND_PORT%
echo.
echo Keep the backend and frontend windows open while using the app.

start "" "http://%APP_HOST%:%FRONTEND_PORT%"

goto end

:failed
echo.
echo [start] Startup failed with exit code %STARTUP_EXIT_CODE%.
echo [start] The command window will stay open so you can read the error.
pause
goto end

:port_listening
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$port = [int]$env:CHECK_PORT; if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { exit 0 } exit 1"
exit /b %ERRORLEVEL%

:end
endlocal & exit /b %STARTUP_EXIT_CODE%
