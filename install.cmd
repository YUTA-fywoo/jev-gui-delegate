@echo off
setlocal
set "PYTHONUTF8=1"
if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" "%~dp0install.py"
) else (
  py -3.12 --version >nul 2>&1
  if not errorlevel 1 (
    py -3.12 "%~dp0install.py"
  ) else (
    "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" "%~dp0install.py"
  )
)
exit /b %errorlevel%
