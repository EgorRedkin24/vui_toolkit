@echo off
REM VUI ToolKit (web UI, site design). ASCII-only: cmd mis-parses Cyrillic in batch files.
cd /d "%~dp0"
start "VUI ToolKit" cmd /k "python main.py"
