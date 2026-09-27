@echo off
setlocal
set "PYTHONUTF8=1"
call "%~dp0install.cmd"
if errorlevel 1 exit /b %errorlevel%
call "%~dp0gui-install.cmd"
exit /b %errorlevel%
