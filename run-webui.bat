@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "PYTHON_BIN=%PROJECT_DIR%.venv\Scripts\python.exe"

if not exist "%PYTHON_BIN%" (
  echo .venv was not found. Create it and install requirements.txt as described in the README.
  exit /b 1
)

"%PYTHON_BIN%" "%PROJECT_DIR%webui\server.py" %*
endlocal
