@echo off
cd /d "%~dp0"
".\backend\.venv\Scripts\python.exe" -m uvicorn backend.main:app --reload > backend.full.log 2>&1
