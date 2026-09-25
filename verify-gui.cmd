@echo off
cd /d C:\jev\jev-bridge
"C:\jev\jev-bridge\.venv\Scripts\python.exe" -X utf8 -m gui_delegate.verify %*
