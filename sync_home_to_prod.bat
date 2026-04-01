@echo off
setlocal EnableExtensions EnableDelayedExpansion

echo ================================
echo UTS DB SYNC: HOME -> PROD (RDS SAFE)
echo ================================

REM ===== MYSQL BIN =====
set "MYSQL_BIN=C:\Program Files\MySQL\MySQL Server 8.0\bin"
set "MYSQL=%MYSQL_BIN%\mysql.exe"
set "MYSQLDUMP=%MYSQL_BIN%\mysqldump.exe"

REM ===== CONFIG =====
set "HOME_DB=uts_db"
set "PROD_DB=user_trial_system_v1"

set "HOME_HOST=192.168.50.68"
set "PROD_HOST=user-trial-database.cblvpmltfuj8.eu-west-1.rds.amazonaws.com"

set "HOME_PORT=3306"
set "PROD_PORT=3306"

set "HOME_USER=root"
set "PROD_USER=admin"

REM ===== PASSWORDS =====
REM Put your real passwords back in these two lines.
set "HOME_PASS=aonlee266533"
set "PROD_PASS=PybrYdBwe"

REM ===== FILES =====
set "DUMP_FILE=home_full_dump.sql"
set "BACKUP_FILE=prod_backup_before_sync.sql"

REM ===== SANITY CHECKS =====
if not exist "%MYSQL%" (
    echo [ERROR] mysql.exe not found at:
    echo %MYSQL%
    pause
    exit /b 1
)

if not exist "%MYSQLDUMP%" (
    echo [ERROR] mysqldump.exe not found at:
    echo %MYSQLDUMP%
    pause
    exit /b 1
)

echo.
echo WARNING: This will WIPE ALL TABLES in PROD (%PROD_DB%) on %PROD_HOST%
set /p CONFIRM=Type YES to continue: 

if /I not "%CONFIRM%"=="YES" (
    echo Cancelled.
    pause
    exit /b 0
)

echo.
echo Step 1: Dump HOME database...
"%MYSQLDUMP%" ^
  -h %HOME_HOST% ^
  -P %HOME_PORT% ^
  -u %HOME_USER% ^
  -p%HOME_PASS% ^
  --routines ^
  --triggers ^
  --single-transaction ^
  --set-gtid-purged=OFF ^
  --max_allowed_packet=1G ^
  %HOME_DB% > "%DUMP_FILE%"

if errorlevel 1 (
    echo [ERROR] HOME dump failed
    pause
    exit /b 1
)

echo.
echo Step 2: Backup PROD database...
"%MYSQLDUMP%" ^
  -h %PROD_HOST% ^
  -P %PROD_PORT% ^
  --ssl-mode=REQUIRED ^
  -u %PROD_USER% ^
  -p%PROD_PASS% ^
  --routines ^
  --triggers ^
  --single-transaction ^
  --set-gtid-purged=OFF ^
  --max_allowed_packet=1G ^
  %PROD_DB% > "%BACKUP_FILE%"

if errorlevel 1 (
    echo [ERROR] PROD backup failed
    pause
    exit /b 1
)

echo.
echo Step 3: Generate DROP script for PROD tables...

del /q prod_tables.txt 2>nul
del /q prod_drop_all_tables.sql 2>nul

REM Get table list into file
"%MYSQL%" ^
-h %PROD_HOST% ^
-P %PROD_PORT% ^
--ssl-mode=REQUIRED ^
-u %PROD_USER% ^
-p%PROD_PASS% ^
-N ^
-e "SHOW TABLES FROM %PROD_DB%;" > prod_tables.txt

IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to fetch table list
    pause
    exit /b 1
)

REM Build drop script
echo SET FOREIGN_KEY_CHECKS=0; > prod_drop_all_tables.sql

FOR /F "delims=" %%t IN (prod_tables.txt) DO (
    echo DROP TABLE IF EXISTS `%%t`;>> prod_drop_all_tables.sql
)

echo SET FOREIGN_KEY_CHECKS=1; >> prod_drop_all_tables.sql

echo.
echo Step 4: Drop ALL tables in PROD...
"%MYSQL%" ^
  -h %PROD_HOST% ^
  -P %PROD_PORT% ^
  --ssl-mode=REQUIRED ^
  -u %PROD_USER% ^
  -p%PROD_PASS% ^
  %PROD_DB% < prod_drop_all_tables.sql

if errorlevel 1 (
    echo [ERROR] Failed to clear PROD tables
    pause
    exit /b 1
)

echo.
echo Step 5: Restore HOME -> PROD...
"%MYSQL%" ^
  -h %PROD_HOST% ^
  -P %PROD_PORT% ^
  --ssl-mode=REQUIRED ^
  -u %PROD_USER% ^
  -p%PROD_PASS% ^
  --max_allowed_packet=1G ^
  %PROD_DB% < "%DUMP_FILE%"

if errorlevel 1 (
    echo [ERROR] Restore failed
    pause
    exit /b 1
)

echo.
echo ================================
echo SUCCESS: PROD now matches HOME exactly
echo ================================
pause
exit /b 0