@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call setup.bat
if errorlevel 1 exit /b 1
start "WiFi Soundboard Server Control" ".venv\Scripts\pythonw.exe" server_control.py
endlocal
