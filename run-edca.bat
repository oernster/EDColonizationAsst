@echo off
setlocal

rem Log file next to this script
set "LOG=%~dp0run-edca.log"
echo ==== %date% %time% ==== >> "%LOG%"

echo Elite: Dangerous Colonisation Assistant
echo ---------------------------------------
echo Initialising, please wait...

rem Change to install root (directory of this script)
cd /d "%~dp0"

rem --- Prefer packaged runtime EXE (no dev environment required) ------
if exist "%~dp0EDColonisationAsst.exe" (
    echo Found packaged runtime EXE, launching... >>"%LOG%"
    "%~dp0EDColonisationAsst.exe"
    goto End
)

rem --- Dev fallback: Check Python -------------------------------------
where python >>"%LOG%" 2>&1
if errorlevel 1 goto NoPython

rem --- Dev fallback: Launch GUI launcher ------------------------------
echo Starting GUI launcher via python backend\src\launcher.py... >>"%LOG%"
python backend\src\launcher.py >>"%LOG%" 2>&1
goto End

rem --- Error handlers -------------------------------------------------

:NoPython
echo. >>"%LOG%"
echo Python 3 is required but was not found in PATH. >>"%LOG%"
echo Please install Python 3.10+ from https://www.python.org/downloads/ and try again. >>"%LOG%"
exit /b 1

:End
endlocal