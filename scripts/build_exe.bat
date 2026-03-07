@echo off
echo Installing dependencies...
cd /d "%~dp0.."

echo Trying with py launcher...
py -m pip install -r "requirements.txt"
if %ERRORLEVEL% NEQ 0 (
    echo Error using py. Trying with python...
    python -m pip install -r "requirements.txt"
)
if %ERRORLEVEL% NEQ 0 (
    echo Error installing dependencies.
    pause
    exit /b %ERRORLEVEL%
)

echo Building Panacea EXE...
py -m PyInstaller --noconsole --onefile --name "Panacea" --icon="assets\panacea_icon.ico" --add-data "assets;assets" --clean --collect-all customtkinter main.py --distpath "dist" --workpath "build" --specpath .
if %ERRORLEVEL% NEQ 0 (
    echo Error using py. Trying with python...
    python -m PyInstaller --noconsole --onefile --name "Panacea" --icon="assets\panacea_icon.ico" --add-data "assets;assets" --clean --collect-all customtkinter main.py --distpath "dist" --workpath "build" --specpath .
)

echo.
echo Build complete. Check the 'dist' folder for Panacea.exe
pause
