@echo off
cd /d "%~dp0"
title Pokemon LLM Bridge Server
echo Starting Local Pokemon LLM Bridge Server on http://127.0.0.1:8008 ...
python server.py
pause
