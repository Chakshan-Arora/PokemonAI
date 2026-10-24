@echo off
set GODOT_EXE=C:\Users\pooja\Downloads\Godot_v4.7.2-stable_win64.exe\Godot_v4.7.2-stable_win64.exe
set PROJECT_DIR=%~dp0Godot\syntax-error-26

if not exist "%GODOT_EXE%" (
    echo Godot executable not found at %GODOT_EXE%
    pause
    exit /b 1
)

echo [1/2] Checking Python Backend Server (http://127.0.0.1:8008)...
netstat -ano | findstr 127.0.0.1:8008 >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Starting Python Backend Server in background...
    start "PokemonAI Backend Server" /min python server.py
    timeout /t 2 /nobreak >nul
) else (
    echo Python Backend Server is already active and running.
)

echo [2/2] Launching Godot 3D Game...
start "" "%GODOT_EXE%" --path "%PROJECT_DIR%"
