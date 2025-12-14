@echo off
setlocal enabledelayedexpansion

REM ===========================================================================
REM Build script: Clean, reinstall, and build EDCA Windows runtime + installer
REM ===========================================================================
REM This script should be run from anywhere; it will cd to the script directory,
REM then:
REM   1. Clean backend/frontend envs and artefacts
REM   2. Recreate backend venv and install requirements-dev (incl. Nuitka)
REM   3. Install frontend deps and run npm run build
REM   4. Build EDColonizationAsst.exe (runtime) via buildruntime.py
REM   5. Build EDColonizationAsstInstaller.exe (GUI installer) via buildguiinstaller.py
REM ===========================================================================

REM Resolve project root to the directory of this script
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%" || (
    echo [ERROR] Failed to cd to script directory "%SCRIPT_DIR%".
    exit /b 1
)

echo.
echo ==============================================
echo  EDCA Windows Runtime + Installer Build Script
echo ==============================================
echo Project root: "%CD%"
echo.

REM ---------------------------------------------------------------------------
REM 0. Kill running EDCA-related processes to avoid file locks
REM ---------------------------------------------------------------------------

REM These taskkill calls are best-effort and ignore failures. They are here to
REM prevent "access is denied" errors when cleaning frontend/node_modules and
REM log files if EDCA or its dev servers are still running.
REM
REM NOTE: This will kill EDCA runtimes and any Node/python processes that match
REM these image names, so avoid running unrelated node/python work while
REM invoking this script.

for %%P in (
    EDColonizationAsst.exe
    EDColonizationAsstInstaller.exe
) do (
    taskkill /IM "%%P" /F /T >nul 2>&1
)

REM Optionally stop node and python globally to clear any lingering dev servers
REM or tray/launcher processes that might hold files in this repo.
for %%P in (
    node.exe
    python.exe
) do (
    taskkill /IM "%%P" /F /T >nul 2>&1
)

REM ---------------------------------------------------------------------------
REM 1. Sanity checks for tools
REM ---------------------------------------------------------------------------

where uv >nul 2>&1
if errorlevel 1 (
    echo [WARN] uv not found on PATH.
    echo        Attempting automatic install via PowerShell...
    echo.

    where powershell >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] PowerShell not found; cannot auto-install uv.
        echo         Install uv from https://docs.astral.sh/uv/getting-started/
        exit /b 1
    )

    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "try { irm https://astral.sh/uv/install.ps1 | iex } catch { exit 1 }"
    if errorlevel 1 (
        echo [ERROR] Automatic uv installation failed.
        echo         Install uv manually from https://docs.astral.sh/uv/getting-started/
        exit /b 1
    )

    where uv >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] uv still not found on PATH after attempted install.
        echo         You may need to restart your shell after installation.
        exit /b 1
    )
)

where npm >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm not found on PATH.
    echo         Install Node.js 18+ from https://nodejs.org/
    exit /b 1
)

REM ---------------------------------------------------------------------------
REM 1. Global cleanup (backend + frontend + build artefacts)
REM ---------------------------------------------------------------------------

echo [CLEAN] Removing backend venv and caches...

REM Backend venv
if exist "backend\.venv" (
    rmdir /s /q "backend\.venv"
)

REM Backend colonization DB (runtime-created)
if exist "backend\src\colonization.db" (
    del /f /q "backend\src\colonization.db"
)

REM Python __pycache__ under backend
for /r "backend" %%D in (.) do (
    if /i "%%~nxD"=="__pycache__" (
        rmdir /s /q "%%D" 2>nul
    )
)

echo [CLEAN] Removing Nuitka / installer build directories and EXEs...

REM Nuitka / build artefacts
for %%D in (
    build
    build_payload
    guiinstaller.build
    guiinstaller.dist
    guiinstaller.onefile-build
    runtime_entry.build
    runtime_entry.dist
    runtime_entry.onefile-build
) do (
    if exist "%%D" (
        rmdir /s /q "%%D"
    )
)

REM Final EXEs
for %%F in (
    EDColonizationAsst.exe
    EDColonizationAsstInstaller.exe
) do (
    if exist "%%F" del /f /q "%%F"
)

REM Logs / tray pid
for %%F in (
    guiinstaller.log
    run-edca.log
    frontend-dev.log
    tray.pid
) do (
    if exist "%%F" del /f /q "%%F"
)

echo [CLEAN] Removing frontend artefacts...

pushd frontend >nul
if exist "node_modules" (
    rmdir /s /q "node_modules"
)
if exist "dist" (
    rmdir /s /q "dist"
)
REM Common frontend caches (ignore errors)
if exist ".vite" rmdir /s /q ".vite"
if exist ".turbo" rmdir /s /q ".turbo"
if exist ".cache" rmdir /s /q ".cache"
popd >nul

echo [CLEAN] Done.
echo.

REM ---------------------------------------------------------------------------
REM 2. Backend: venv + requirements-dev (incl. Nuitka, PySide6, shiboken6)
REM ---------------------------------------------------------------------------

echo [BACKEND] Creating virtual environment with uv venv .venv ...

pushd backend >nul
uv venv .venv
if errorlevel 1 (
    echo [ERROR] uv venv .venv failed.
    popd >nul
    exit /b 1
)

echo [BACKEND] Installing requirements-dev.txt via uv pip ...

uv pip install -r requirements-dev.txt
if errorlevel 1 (
    echo [ERROR] uv pip install -r requirements-dev.txt failed.
    popd >nul
    exit /b 1
)
popd >nul

echo [BACKEND] Backend environment ready.
echo.

REM ---------------------------------------------------------------------------
REM 3. Frontend: npm install + security fixes + npm run build
REM ---------------------------------------------------------------------------

echo [FRONTEND] Installing npm dependencies...

pushd frontend >nul
call npm install
if errorlevel 1 (
    echo [ERROR] npm install failed in frontend/.
    popd >nul
    exit /b 1
)

echo [FRONTEND] Creating package-lock.json for audit...

call npm i --package-lock-only
if errorlevel 1 (
    echo [ERROR] npm i --package-lock-only failed in frontend/.
    popd >nul
    exit /b 1
)

echo [FRONTEND] Running npm audit fix --force to apply security fixes...

call npm audit fix --force
if errorlevel 1 (
    echo [ERROR] npm audit fix --force failed in frontend/.
    popd >nul
    exit /b 1
)

echo [FRONTEND] Running npm run build (tsc && vite build)...

call npm run build
if errorlevel 1 (
    echo [ERROR] npm run build failed in frontend/.
    popd >nul
    exit /b 1
)
popd >nul

echo [FRONTEND] Frontend production bundle built (frontend/dist) with audit fixes applied.
echo.

REM ---------------------------------------------------------------------------
REM 4. Build runtime EXE (EDColonizationAsst.exe) via Nuitka
REM ---------------------------------------------------------------------------

echo [RUNTIME] Building EDColonizationAsst.exe via buildruntime.py ...

REM Use the backend venv Python created by uv venv so that Nuitka and all
REM backend dependencies are available.
set "BACKEND_PY=backend\.venv\Scripts\python.exe"
if not exist "%BACKEND_PY%" (
    echo [ERROR] Backend venv python not found at "%BACKEND_PY%".
    echo         Ensure the backend environment step completed successfully.
    exit /b 1
)

"%BACKEND_PY%" buildruntime.py
if errorlevel 1 (
    echo [ERROR] buildruntime.py failed when invoked with "%BACKEND_PY%".
    exit /b 1
)

if not exist "EDColonizationAsst.exe" (
    echo [WARN] buildruntime.py completed but EDColonizationAsst.exe was not found.
    echo        Check the buildruntime output above for details.
) else (
    echo [RUNTIME] Built runtime: "%CD%\EDColonizationAsst.exe"
)

echo.

REM ---------------------------------------------------------------------------
REM 5. Build GUI installer EXE (EDColonizationAsstInstaller.exe)
REM ---------------------------------------------------------------------------

echo [INSTALLER] Building EDColonizationAsstInstaller.exe via buildguiinstaller.py ...

"%BACKEND_PY%" buildguiinstaller.py
if errorlevel 1 (
    echo [ERROR] buildguiinstaller.py failed when invoked with "%BACKEND_PY%".
    exit /b 1
)

if not exist "EDColonizationAsstInstaller.exe" (
    echo [WARN] buildguiinstaller.py completed but EDColonizationAsstInstaller.exe was not found.
    echo        Check the buildguiinstaller output above for details.
) else (
    echo [INSTALLER] Built installer: "%CD%\EDColonizationAsstInstaller.exe"
)

echo.
echo ====================================================
echo  Build pipeline complete.
echo  Runtime  : "%CD%\EDColonizationAsst.exe"
echo  Installer: "%CD%\EDColonizationAsstInstaller.exe"
echo ====================================================
echo.
echo You can now run the installer by double-clicking:
echo   "%CD%\EDColonizationAsstInstaller.exe"
echo or from this shell (PowerShell):
echo   Start-Process .\EDColonizationAsstInstaller.exe
echo.

endlocal