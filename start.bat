@echo off
REM Double-click to start PokePlay (mGBA with the bridge script and Ollama must already be running).
cd /d "%~dp0"
if not exist config.toml copy config.example.toml config.toml >nul
python -m pokeplay %*
pause
