@echo off
setlocal

set "BACKEND_PORT=%~1"
set "FRONTEND_PORT=%~2"

if "%BACKEND_PORT%"=="" set "BACKEND_PORT=8000"
if "%FRONTEND_PORT%"=="" set "FRONTEND_PORT=3000"

cd /d "%~dp0..\frontend\next-web"
set "NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:%BACKEND_PORT%"

npm.cmd run dev -- --hostname 127.0.0.1 --port %FRONTEND_PORT%
