@echo off
chcp 65001 >nul
rem JARVIS: окно на компьютере + Telegram (если в jarvis\.env вписан TELEGRAM_BOT_TOKEN).
rem Это чёрное окно не закрывайте — пока оно открыто, JARVIS работает.
cd /d "%~dp0"
set PYTHONPATH=%~dp0core
"%~dp0..\.venv\Scripts\python.exe" -m jarviscore.app
pause
