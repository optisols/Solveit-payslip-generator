@echo off
title 🔧 Building SOLVEIT Payslip Production App
color 0E
echo ======================================================
echo   🚀 SOLVEIT PAYSLIP PRODUCTION BUILD - ONE CLICK
echo ======================================================
echo.

REM -------------------------
REM Configure version here
REM -------------------------
set "APP_VERSION=1.3"

REM -------------------------
REM Paths (adjust if needed)
REM -------------------------
set "PROJECT_DIR=C:\Projects\payslip"
set "SPEC_FILE=%PROJECT_DIR%\app.spec"
set "DIST_DIR=%PROJECT_DIR%\dist"
set "OUTPUT_SUBDIR=PayslipApp"
set "DEFAULT_EXE_NAME=PayslipApp.exe"

REM -------------------------
REM Date for filename (YYYY-MM-DD)
REM -------------------------
for /f "tokens=1-3 delims=/- " %%a in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "TODAY=%%a-%%b-%%c"

REM -------------------------
REM Start build
REM -------------------------
cd /d "%PROJECT_DIR%"

echo 🧹 Cleaning old build folders...
rmdir /s /q "%DIST_DIR%" >nul 2>&1
rmdir /s /q build >nul 2>&1
del /f /q "%PROJECT_DIR%\app.spec.lock" >nul 2>&1
echo ✅ Old build files cleaned.
echo.

echo 🎨 Building React frontend...
cd "%PROJECT_DIR%\frontend"
call npm run build
if %errorlevel% neq 0 (
    echo ❌ React build failed! Check your React errors.
    pause
    exit /b %errorlevel%
)
echo ✅ React build completed.
echo.

cd /d "%PROJECT_DIR%"

echo ⚙️  Running PyInstaller (clean)...
pyinstaller --clean "%SPEC_FILE%"
if %errorlevel% neq 0 (
    echo ❌ PyInstaller build failed! Check logs above.
    pause
    exit /b %errorlevel%
)
echo ✅ PyInstaller build completed.
echo.

REM -------------------------
REM Locate produced EXE
REM -------------------------
set "BUILT_EXE=%PROJECT_DIR%\dist\%OUTPUT_SUBDIR%\%DEFAULT_EXE_NAME%"
if NOT exist "%BUILT_EXE%" (
    REM try onefile style (dist\PayslipApp.exe)
    set "BUILT_EXE=%PROJECT_DIR%\dist\PayslipApp.exe"
)

if NOT exist "%BUILT_EXE%" (
    echo ❌ Built EXE not found. Look into %PROJECT_DIR%\dist for output.
    pause
    exit /b 2
)

REM -------------------------
REM New filename with version and date
REM -------------------------
set "NEW_EXE_NAME=PayslipApp_v%APP_VERSION%_%TODAY%.exe"
set "NEW_EXE_PATH=%PROJECT_DIR%\dist\%NEW_EXE_NAME%"

echo 📁 Renaming and moving final EXE:
echo   From: "%BUILT_EXE%"
echo   To:   "%NEW_EXE_PATH%"

REM If target exists, remove it first
if exist "%NEW_EXE_PATH%" del /f /q "%NEW_EXE_PATH%"

move /Y "%BUILT_EXE%" "%NEW_EXE_PATH%" >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️ Could not move/rename EXE. Attempting copy instead...
    copy /Y "%BUILT_EXE%" "%NEW_EXE_PATH%" >nul 2>&1
    if %errorlevel% neq 0 (
        echo ❌ Failed to copy EXE. Check permissions.
        pause
        exit /b 3
    )
)

echo ✅ Final executable ready:
echo   %NEW_EXE_PATH%
echo.

REM -------------------------
REM Optionally run the new EXE
REM -------------------------
set /p runnow="▶️  Do you want to run the new EXE now? (Y/N): "
if /i "%runnow%"=="Y" (
    echo 🚀 Launching the Payslip App...
    start "" "%NEW_EXE_PATH%"
) else (
    echo ✅ Build finished. You can run the EXE from the dist folder.
)

echo.
pause
