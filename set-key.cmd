@echo off
setlocal
set "PYTHONUTF8=1"
"%~dp0.venv\Scripts\pythonw.exe" "%~dp0scripts\set-key.py"
exit /b %errorlevel%
