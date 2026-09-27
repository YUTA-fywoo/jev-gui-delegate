@echo off
cd /d "%~dp0"
"%~dp0.venv\Scripts\python.exe" -X utf8 -m gui_delegate.install install
if errorlevel 1 exit /b %errorlevel%
"%~dp0.venv\Scripts\python.exe" -X utf8 -m gui_delegate.cli clear-stop
