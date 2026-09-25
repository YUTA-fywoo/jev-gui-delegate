@echo off
cd /d C:\jev\jev-bridge
"C:\jev\jev-bridge\.venv\Scripts\python.exe" -X utf8 -m gui_delegate.install install
if errorlevel 1 exit /b %errorlevel%
"C:\jev\jev-bridge\.venv\Scripts\python.exe" -X utf8 -m gui_delegate.cli clear-stop
