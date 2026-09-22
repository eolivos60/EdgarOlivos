@echo off
setlocal
set LOG_FILE=C:\Users\eolivos\OneDrive - Cisco\Documents\GitHub\Cisco-Meraki-Agentic-Workflow-MCP-Server\mcp_launcher.log
echo [%date% %time%] launcher invoked >> "%LOG_FILE%"
"C:\Users\eolivos\OneDrive - Cisco\Documents\GitHub\Cisco-Meraki-Agentic-Workflow-MCP-Server\.venv\Scripts\python.exe" "C:\Users\eolivos\OneDrive - Cisco\Documents\GitHub\Cisco-Meraki-Agentic-Workflow-MCP-Server\server.py" >> "%LOG_FILE%" 2>&1
echo [%date% %time%] launcher exited code %errorlevel% >> "%LOG_FILE%"
endlocal
