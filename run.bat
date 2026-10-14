@echo off
REM Cyberfield AI - WhatsApp Assistant: one-click local run (Windows)
cd /d %~dp0
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
if not exist frontend\dist ( pushd frontend & call npm install & call npm run build & popd )
echo.
echo  Open http://127.0.0.1:8000 in your browser
echo.
cd backend
python -m uvicorn app.main:app --port 8000
