@echo off
title User Trials Server

REM ============================================
REM CONFIG
REM ============================================
set PROJECT_ROOT=C:\sites\ut_site
set PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe

REM ============================================
REM Move to project root
REM ============================================
cd /d %PROJECT_ROOT%

REM ============================================
REM Run with explicit interpreter
REM ============================================
echo Using Python:
%PYTHON% -c "import sys; print(sys.executable)"

echo Starting server...
%PYTHON% -m app.main

echo.
echo Server stopped.
pause