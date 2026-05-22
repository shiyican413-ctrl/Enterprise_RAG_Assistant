@echo off
setlocal

cd /d "%~dp0.."

set "BACKEND_PORT=8000"
set "FRONTEND_PORT=3000"

if not exist ".venv\Scripts\python.exe" (
  echo [start] Creating Python virtual environment...
  python -m venv .venv
  if errorlevel 1 goto failed
)

echo [start] Installing backend dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed

if not exist "frontend\next-web\node_modules" (
  echo [start] Installing frontend dependencies...
  pushd "frontend\next-web"
  call npm.cmd install
  if errorlevel 1 goto failed
  popd
) else (
  echo [start] Frontend dependencies already exist. Skipping npm install.
)

echo [start] Starting backend on http://127.0.0.1:%BACKEND_PORT%
start "Enterprise RAG Backend" cmd /k call "%~dp0start-backend.bat" %BACKEND_PORT%

echo [start] Starting frontend on http://127.0.0.1:%FRONTEND_PORT%
start "Enterprise RAG Frontend" cmd /k call "%~dp0start-frontend.bat" %BACKEND_PORT% %FRONTEND_PORT%

echo.
echo Backend:  http://127.0.0.1:%BACKEND_PORT%
echo API docs: http://127.0.0.1:%BACKEND_PORT%/docs
echo Frontend: http://127.0.0.1:%FRONTEND_PORT%
echo.
echo Keep the backend and frontend windows open while using the app.

timeout /t 5 /nobreak >nul
start "" "http://127.0.0.1:%FRONTEND_PORT%"

goto end

:failed
echo.
echo [start] Startup failed. Please check the error above.
pause

:end
endlocal
