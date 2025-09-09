# Run FastAPI via venv with dotenv
$ErrorActionPreference = 'Stop'
$root = Join-Path $PSScriptRoot '..'
$venvPy = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPy)) { throw ".venv not found at $venvPy" }
$envFile = Join-Path $root '.env'
& $venvPy -m uvicorn --env-file $envFile api.main:app --reload @Args

