@echo off
echo Installing dependencies...
cd /d "%~dp0.."
pip install -r "requirements.txt"
if %ERRORLEVEL% NEQ 0 (
    echo Error using pip directly. Trying with python -m pip...
    python -m pip install -r "requirements.txt"
)
if %ERRORLEVEL% NEQ 0 (
    echo Error installing dependencies.
    pause
    exit /b %ERRORLEVEL%
)

echo Building Panacea EXE...
python scripts\build.py
if %ERRORLEVEL% NEQ 0 (
    echo Build failed. No release should be published.
    pause
    exit /b %ERRORLEVEL%
)
echo.
echo Build complete. Check the 'dist' folder for Panacea.exe
pause
