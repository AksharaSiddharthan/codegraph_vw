@echo off
REM CodeGraph Windows launcher. Starts backend + frontend in separate windows.
REM Prereq: Ollama running with qwen2.5-coder:7b pulled.

cd /d "%~dp0"

cd backend
if not exist ".venv" (
  echo [CodeGraph] Creating Python venv...
  python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
echo [CodeGraph] Starting backend on :8000 in new window...
start "CodeGraph Backend" cmd /k ".venv\Scripts\activate.bat && python main.py"
cd ..

cd frontend
if not exist "node_modules" (
  echo [CodeGraph] Installing frontend deps...
  call npm install
)
echo [CodeGraph] Starting frontend on :5173 in new window...
start "CodeGraph Frontend" cmd /k "npm run dev"
cd ..

echo.
echo [CodeGraph] Both servers launching. Open http://localhost:5173 once they're up.
echo [CodeGraph] Close the two new terminal windows to stop the servers.
pause
