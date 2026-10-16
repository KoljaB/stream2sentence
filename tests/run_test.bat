@echo off
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" tools\run_release_checks.py
) else (
    python tools\run_release_checks.py
)
exit /b %errorlevel%
