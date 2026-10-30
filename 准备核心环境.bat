@echo off
chcp 65001 >nul
cd /d "%~dp0"
set /p "MANGA_ROOT=请输入全新便携版根目录（不加引号）: "
"%MANGA_ROOT%\python_embeded\python.exe" -s setup_core.py "%MANGA_ROOT%"
pause
