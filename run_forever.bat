@echo off
REM Unattended mode: starts PokePlay and restarts it automatically if it ever stops or crashes.
REM Close this window to stop her for real.
cd /d "%~dp0"
if not exist config.toml copy config.example.toml config.toml >nul
:loop
echo [%date% %time%] Starting PokePlay...
python -m pokeplay
echo [%date% %time%] PokePlay stopped. Restarting in 15 seconds (close this window to stop)...
timeout /t 15 /nobreak >nul
goto loop
