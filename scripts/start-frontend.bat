@echo off
setlocal EnableExtensions
set "FRONTEND_EXIT_CODE=0"

set "BACKEND_PORT=%~1"
set "FRONTEND_PORT=%~2"

if "%BACKEND_PORT%"=="" set "BACKEND_PORT=8000"
if "%FRONTEND_PORT%"=="" set "FRONTEND_PORT=3001"

cd /d "%~dp0..\frontend\next-web"
set "NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:%BACKEND_PORT%"

if exist "node_modules\.bin\next.cmd" (
  call "node_modules\.bin\next.cmd" dev --hostname 127.0.0.1 --port "%FRONTEND_PORT%"
) else (
  call npm.cmd run dev -- --hostname 127.0.0.1 --port "%FRONTEND_PORT%"
)
set "FRONTEND_EXIT_CODE=%ERRORLEVEL%"

if not "%FRONTEND_EXIT_CODE%"=="0" goto failed

goto end

:failed
echo.
echo [frontend] Next.js exited with code %FRONTEND_EXIT_CODE%.
echo [frontend] Review the error above. This window will stay open when launched from start.bat.

:end
endlocal & exit /b %FRONTEND_EXIT_CODE%
