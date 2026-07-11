@echo off
REM OpenMontage Web SaaS — start backend + frontend
REM Usage: double-click or run from repo root
REM NOTE: port 8000 may be used by another service; we use 8001.

echo.
echo ============================================================
echo  OpenMontage Web SaaS — Starting Services
echo ============================================================
echo.

REM ── Backend (FastAPI on port 8001) ────────────────────────
echo [1/2] Starting FastAPI backend on http://localhost:8001 ...
start "OpenMontage API" cmd /k "cd /d %~dp0 && .venv\Scripts\pip install -q -r web_api\requirements.txt && .venv\Scripts\uvicorn web_api.main:app --reload --port 8001"

timeout /t 3 /nobreak >nul

REM ── Frontend (Vite dev server on port 5173) ───────────────
echo [2/2] Starting React frontend on http://localhost:5173 ...
start "OpenMontage UI" cmd /k "cd /d %~dp0\web_ui && npm run dev"

echo.
echo ============================================================
echo  Backend:  http://localhost:8001
echo  Frontend: http://localhost:5173
echo  API Docs: http://localhost:8001/api/docs
echo ============================================================
echo.
echo Press any key to exit this launcher (services keep running).
pause >nul
