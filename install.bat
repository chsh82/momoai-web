@echo off
echo ================================================
echo MOMOAI v3.3.0 Web Edition - Installation
echo ================================================
echo.

echo [1/4] Installing Python packages...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install Python packages
    pause
    exit /b 1
)
echo.

echo [2/4] Installing Playwright Chromium...
playwright install chromium
if %errorlevel% neq 0 (
    echo ERROR: Failed to install Playwright
    pause
    exit /b 1
)
echo.

echo [3/4] Checking API key...
if "%ANTHROPIC_API_KEY%"=="" (
    echo WARNING: ANTHROPIC_API_KEY environment variable is not set
    echo Please set it using:
    echo   setx ANTHROPIC_API_KEY "your-api-key-here"
    echo.
    set /p "CONTINUE=Do you want to set it now? (y/n): "
    if /i "%CONTINUE%"=="y" (
        set /p "API_KEY=Enter your Anthropic API key: "
        setx ANTHROPIC_API_KEY "%API_KEY%"
        echo API key set! Please restart this terminal and run install.bat again.
        pause
        exit /b 0
    )
) else (
    echo API key found: %ANTHROPIC_API_KEY:~0,20%...
)
echo.

echo [4/4] Creating directories...
if not exist "outputs\html" mkdir "outputs\html"
if not exist "outputs\pdf" mkdir "outputs\pdf"
if not exist "uploads" mkdir "uploads"
echo.

echo ================================================
echo Installation Complete!
echo ================================================
echo.
echo To start the server, run:
echo   python app.py
echo.
echo Then open your browser to:
echo   http://localhost:5000
echo.
echo For more information, see README.md or QUICKSTART.md
echo ================================================
pause
