@echo off
setlocal EnableExtensions
set "PYTHONUTF8=1"

cd /d "%~dp0.."
set "MILVUS_COMPOSE=docker\milvus\docker-compose.yml"
set "HEALTH_TIMEOUT=180"
set "CONTAINER=milvus-standalone"

echo [milvus] Ensuring Milvus is running...

REM 1. Docker available?
where docker >nul 2>&1
if errorlevel 1 (
  echo [milvus] WARNING: docker not found. Skipping Milvus startup.
  echo [milvus]          Install Docker Desktop, or set VECTOR_STORE_BACKEND=local in .env.
  exit /b 1
)
docker info >nul 2>&1
if errorlevel 1 (
  echo [milvus] WARNING: Docker daemon is not running. Skipping Milvus startup.
  echo [milvus]          Start Docker Desktop first.
  exit /b 1
)

REM 2. Compose file present?
if not exist "%MILVUS_COMPOSE%" (
  echo [milvus] WARNING: %MILVUS_COMPOSE% not found. Skipping Milvus startup.
  exit /b 1
)

REM 3. Already healthy? (PowerShell query avoids cmd pipe / findstr / port-check quirks)
call :is_healthy && (
  echo [milvus] Milvus already running and healthy.
  exit /b 0
)

REM 4. Start via docker compose (idempotent; pulls images on first run).
echo [milvus] Starting Milvus via docker compose ^(first run may take a few minutes^)...
docker compose -f "%MILVUS_COMPOSE%" up -d
if errorlevel 1 (
  echo [milvus] ERROR: docker compose up failed.
  echo [milvus]        Run: docker compose -f %MILVUS_COMPOSE% logs
  exit /b 1
)

REM 5. Wait for healthy.
echo [milvus] Waiting for Milvus to become healthy ^(up to %HEALTH_TIMEOUT%s^)...
set "ELAPSED=0"
:wait_health
call :is_healthy && (
  echo [milvus] Milvus is healthy.
  exit /b 0
)
call :is_running || (
  echo [milvus] ERROR: %CONTAINER% container is not running.
  echo [milvus]        Run: docker compose -f %MILVUS_COMPOSE% logs milvus
  exit /b 1
)
set /a "ELAPSED+=5"
if %ELAPSED% geq %HEALTH_TIMEOUT% (
  echo [milvus] WARNING: Milvus not healthy after %HEALTH_TIMEOUT%s. It may still be booting.
  echo [milvus]          Check: docker compose -f %MILVUS_COMPOSE% logs milvus
  exit /b 1
)
timeout /t 5 /nobreak >nul
goto wait_health

:is_healthy
powershell -NoProfile -Command "$h = (docker inspect -f '{{.State.Health.Status}}' %CONTAINER% 2>$null) -join ''; if ($h.Trim() -eq 'healthy') { exit 0 } else { exit 1 }"
exit /b %ERRORLEVEL%

:is_running
powershell -NoProfile -Command "$r = (docker inspect -f '{{.State.Running}}' %CONTAINER% 2>$null) -join ''; if ($r.Trim() -eq 'true') { exit 0 } else { exit 1 }"
exit /b %ERRORLEVEL%
