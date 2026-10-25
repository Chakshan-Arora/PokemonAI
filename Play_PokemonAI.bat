@echo off
cd /d "%~dp0"
title Pokemon AI Launcher
echo Starting Pokemon AI Server in background...
start "Pokemon Server" /min cmd /c "python server.py"
timeout /t 2 >nul
echo Launching Pokemon AI Game...
start "" PokemonAI.exe
