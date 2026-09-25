@echo off
setlocal
set "PYTHONUTF8=1"
set "TYPESAFE_LOG_LEVEL=off"
"%~dp0.venv\Scripts\python.exe" -u "%~dp0server.py"
exit /b %errorlevel%
