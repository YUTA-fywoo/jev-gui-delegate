@echo off
setlocal
set "PYTHONUTF8=1"
"%~dp0.venv\Scripts\python.exe" "%~dp0cli.py" health
exit /b %errorlevel%
