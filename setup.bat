@echo off
REM Double-click to install everything PokePlay needs (Python, mGBA, Ollama, OBS, the AI model).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
pause
