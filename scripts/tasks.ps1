param(
    [ValidateSet('Install','Test','Demo','Labels')]
    [string]$Task = 'Test',
    [string]$Python = 'python'
)

switch ($Task) {
  'Install' { & $Python -m pip install -r requirements.txt; break }
  'Test'    { & $Python -m pytest -q; break }
  'Demo'    { & $Python demo.py; break }
  'Labels'  { & $Python Mesh/tools/build_mastercategories.py; break }
}
