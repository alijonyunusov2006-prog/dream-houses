@echo off
title Jarvis installer
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  Jarvis (OpenJarvis) installer
echo  Details will appear below. Do not close this window until it says it is done.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-jarvis.ps1" %*
echo.
if errorlevel 1 (
    echo  Installation stopped with an error. See the log path above.
) else (
    echo  Done. Jarvis is installed.
)
echo.
pause
