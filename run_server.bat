@echo off
title User Trials Server

REM ============================================
REM CONFIG
REM ============================================
set PORT=8000

REM ============================================
REM Stop server if port is already in use
REM ============================================
for /f "tokens=5" %%p in (
    'netstat -ano ^| findstr :%PORT% ^| findstr LISTENING'
) do (
    echo Existing server detected on port %PORT%. Stopping PID %%p...
    taskkill /PID %%p /F >nul
    timeout /t 1 >nul
)

REM ============================================
REM Move to project root
REM ============================================
cd /d C:\sites\ut_site

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Start the server
python -m app.main

echo.
echo Server stopped.
pause
