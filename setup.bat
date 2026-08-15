@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install Python 3.10 or newer from https://python.org/
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
if errorlevel 1 goto :error

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 goto :error
python -m pip install -r requirements.txt
if errorlevel 1 goto :error

if not exist "sounds" mkdir sounds
echo.
echo Setup complete. Run start_soundboard.bat to launch the soundboard.
pause
exit /b 0

:error
echo.
echo Setup failed. Review the error above.
pause
exit /b 1
