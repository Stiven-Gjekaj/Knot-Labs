$ErrorActionPreference = 'Stop'

# Ensure venv exists
if (-not (Test-Path ..\.venv\Scripts\python.exe)) {
  Write-Host 'Creating .venv'
  python -m venv ..\.venv
}

$py = Resolve-Path ..\.venv\Scripts\python.exe
& $py -m pip install --upgrade pip
if (Test-Path ..\requirements.txt) {
  & $py -m pip install -r ..\requirements.txt
}
Write-Host 'Venv ready at .venv'

