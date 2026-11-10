@echo off
REM VUI ToolKit launcher. ASCII-only: cmd mis-parses Cyrillic in batch files.
choice /C 12 /N /M "[1] Web UI (site design)   [2] Desktop GUI: "
if %ERRORLEVEL%==1 start "VUI ToolKit Web" cmd /k "cd /d "%~dp0VUI ToolKit Web" && python main.py"
if %ERRORLEVEL%==2 start "VUI ToolKit GUI" cmd /k "cd /d "%~dp0VUI ToolKit GUI" && python main.py"
