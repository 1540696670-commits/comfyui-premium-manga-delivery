@echo off
chcp 65001 >nul
cd /d "%~dp0"
set /p "MANGA_ROOT=请输入便携版根目录（不加引号）: "
"%MANGA_ROOT%\python_embeded\python.exe" -s models_tool.py verify "%MANGA_ROOT%\ComfyUI\models"
pause
