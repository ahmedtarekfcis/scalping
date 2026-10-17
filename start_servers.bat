@echo off
echo Starting Backend and Frontend...

:: Check if Windows Terminal is installed
where wt >nul 2>nul
if %errorlevel% equ 0 (
    echo Launching in Windows Terminal...
    start "" wt -d "%~dp0backend" cmd /k "python main.py" ; new-tab -d "%~dp0frontend" cmd /k "npm run dev"
) else (
    echo Windows Terminal not found. Launching in standard command prompts...
    start "Backend" /D "%~dp0backend" cmd /k "python main.py"
    start "Frontend" /D "%~dp0frontend" cmd /k "npm run dev"
)
