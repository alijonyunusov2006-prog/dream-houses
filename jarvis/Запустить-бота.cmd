@echo off
chcp 65001 >nul
rem Бот JARVIS в Telegram. Ключ и номер чата — в jarvis\.env (TELEGRAM_BOT_TOKEN, OWNER_CHAT_ID).
cd /d "%~dp0"
set PYTHONPATH=%~dp0core
"%~dp0..\.venv\Scripts\python.exe" -m jarviscore.bot
pause
