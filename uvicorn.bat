@echo off
setlocal
if not exist ".venv\Scripts\uvicorn.exe" (
  echo .venv uvicorn not found at ".venv\Scripts\uvicorn.exe"
  exit /b 1
)
".venv\Scripts\uvicorn.exe" %*

