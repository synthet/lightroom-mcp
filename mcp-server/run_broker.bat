@echo off
cd /d "%~dp0"
echo Starting Lightroom MCP Broker...
.venv\Scripts\python.exe start_broker.py
pause
