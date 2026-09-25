@echo off
setlocal
set "PYTHONUTF8=1"
"%~dp0.venv\Scripts\python.exe" "%~dp0uninstall.py" %*
exit /b %errorlevel%
