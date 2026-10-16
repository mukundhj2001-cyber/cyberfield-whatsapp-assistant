@echo off
REM Cyberfield AI - WhatsApp Assistant: one-click local run (Windows)
cd /d %~dp0
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt

REM Rebuild the UI on first run and whenever the code changed (e.g. after git pull)
set "REV="
for /f %%i in ('git rev-parse HEAD 2^>nul') do set "REV=%%i"
set "BUILT="
if exist frontend\dist\.rev set /p BUILT=<frontend\dist\.rev
if not exist frontend\dist\index.html goto build
if not "%REV%"=="%BUILT%" goto build
goto run
:build
echo Building the dashboard UI...
pushd frontend
call npm install
call npm run build
popd
if defined REV echo %REV%>frontend\dist\.rev

:run
echo.
echo  Open http://127.0.0.1:8000 in your browser
echo.
cd backend
python -m uvicorn app.main:app --port 8000
