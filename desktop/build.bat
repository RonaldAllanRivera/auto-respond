@echo off
setlocal EnableDelayedExpansion

echo ============================================================
echo  Meet Lessons — Windows Build Script
echo ============================================================
echo.

:: ----------------------------------------------------------------
:: CONFIG — update TESSERACT_INSTALLER to match your downloaded file
:: ----------------------------------------------------------------
set TESSERACT_INSTALLER=tesseract-ocr-w64-setup-5.5.0.20241111.exe
set APP_NAME=MeetLessons
set INNO_COMPILER="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

:: ----------------------------------------------------------------
:: Step 1 — Check prerequisites
:: ----------------------------------------------------------------
echo [1/5] Checking prerequisites...

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.12 from https://www.python.org/downloads/
    echo        Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

if not exist %INNO_COMPILER% (
    echo ERROR: Inno Setup 6 not found at %INNO_COMPILER%
    echo        Download from https://jrsoftware.org/isdl.php
    pause
    exit /b 1
)

if not exist "installer\%TESSERACT_INSTALLER%" (
    echo ERROR: Tesseract installer not found at installer\%TESSERACT_INSTALLER%
    echo        Download from https://github.com/UB-Mannheim/tesseract/wiki
    echo        Place the .exe in the desktop\installer\ folder.
    echo        Then update TESSERACT_INSTALLER at the top of this script.
    pause
    exit /b 1
)

if not exist "assets\icon.ico" (
    echo ERROR: Icon not found at assets\icon.ico
    pause
    exit /b 1
)

echo    OK.
echo.

:: ----------------------------------------------------------------
:: Step 2 — Install Python dependencies
:: ----------------------------------------------------------------
echo [2/5] Installing Python dependencies...
pip install --quiet --upgrade pyinstaller
pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)
echo    OK.
echo.

:: ----------------------------------------------------------------
:: Step 3 — Build .exe with PyInstaller
:: ----------------------------------------------------------------
echo [3/5] Building MeetLessons.exe with PyInstaller...

if exist "dist\%APP_NAME%.exe" del /f /q "dist\%APP_NAME%.exe"
if exist "build" rmdir /s /q build

pyinstaller ^
  --onefile ^
  --windowed ^
  --name %APP_NAME% ^
  --icon assets\icon.ico ^
  --add-data ".env.example;." ^
  main.py

if not exist "dist\%APP_NAME%.exe" (
    echo ERROR: PyInstaller failed — dist\%APP_NAME%.exe not found.
    pause
    exit /b 1
)
echo    OK — dist\%APP_NAME%.exe created.
echo.

:: ----------------------------------------------------------------
:: Step 4 — Update Tesseract filename in .iss script
:: ----------------------------------------------------------------
echo [4/5] Compiling installer with Inno Setup...

:: Patch the TESSERACT_INSTALLER define in the .iss file on the fly
set ISS_ORIG=installer\MeetLessons.iss
set ISS_TEMP=installer\MeetLessons_build.iss

powershell -Command "(Get-Content '%ISS_ORIG%') -replace '#define TESSERACT_INSTALLER \".*\"', '#define TESSERACT_INSTALLER \"%TESSERACT_INSTALLER%\"' | Set-Content '%ISS_TEMP%'"

%INNO_COMPILER% "%ISS_TEMP%"

if exist "%ISS_TEMP%" del /f /q "%ISS_TEMP%"

if not exist "dist\MeetLessonsInstaller.exe" (
    echo ERROR: Inno Setup failed — dist\MeetLessonsInstaller.exe not found.
    pause
    exit /b 1
)
echo    OK — dist\MeetLessonsInstaller.exe created.
echo.

:: ----------------------------------------------------------------
:: Step 5 — Done
:: ----------------------------------------------------------------
echo [5/5] Build complete!
echo.
echo   Output: dist\MeetLessonsInstaller.exe
echo.
echo Next steps:
echo   1. Test on a clean Windows VM (no Python, no Tesseract)
echo   2. Go to GitHub repo ^> Releases ^> Draft a new release
echo   3. Attach dist\MeetLessonsInstaller.exe
echo   4. Copy the download URL
echo   5. Set DESKTOP_DOWNLOAD_URL on Render to that URL
echo.
pause
