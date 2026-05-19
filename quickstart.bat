@echo off
cd /d "%~dp0"
py -3 install.py --quickstart --project-names
if errorlevel 1 python install.py --quickstart --project-names
