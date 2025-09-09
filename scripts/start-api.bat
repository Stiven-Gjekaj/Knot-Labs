@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%\.." >nul 2>&1
if not exist ".venv\Scripts\python.exe" (
  echo .venv python not found at "%CD%\.venv\Scripts\python.exe"
  popd >nul 2>&1
  exit /b 1
)
".venv\Scripts\python.exe" -m uvicorn --env-file ".env" api.main:app --reload %*
set ERR=%ERRORLEVEL%
popd >nul 2>&1
exit /b %ERR%

