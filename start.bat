@echo off
echo ================================================
echo MOMOAI v3.3.0 Web Edition
echo ================================================
echo.

REM Check if API key is set
if "%ANTHROPIC_API_KEY%"=="" (
    echo ERROR: ANTHROPIC_API_KEY environment variable is not set
    echo Please set it using:
    echo   setx ANTHROPIC_API_KEY "your-api-key-here"
    echo.
    echo Or run install.bat to set it up
    pause
    exit /b 1
)

echo Starting MOMOAI server...
echo.
echo Server will be available at: http://localhost:5000
echo Press Ctrl+C to stop the server
echo.
echo ================================================

python app.py
