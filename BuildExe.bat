@echo off
echo Installing dependencies...
pip install -r "%~dp0requirements.txt"
if %ERRORLEVEL% NEQ 0 (
    echo Error installing dependencies.
    pause
    exit /b %ERRORLEVEL%
)

echo Building Panacea EXE...
pyinstaller --noconsole --onefile --name "panacea" --icon="%~dp0panacea_icon.ico" --add-data "%~dp0panacea_icon.ico;." --clean --collect-all customtkinter main.py --distpath "%~dp0dist" --workpath "%~dp0build" --specpath .
echo.
echo Build complete. Check the 'dist' folder for Panacea.exe
pause
