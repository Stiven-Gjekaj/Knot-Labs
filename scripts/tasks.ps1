param(
    [ValidateSet('Install','Test','Demo','GUI','Labels','CLI')]
    [string]$Task = 'CLI',
    [string]$Python = 'python'
)

switch ($Task) {
  'Install' { & $Python -m pip install -r requirements.txt; break }
  'Test'    { & $Python -m pytest -q; break }
  'Demo'    { & $Python demo.py; break }
  'GUI'     { & $Python gui_demo.py; break }
  'Labels'  { & $Python Mesh/tools/build_mastercategories.py; break }
  'CLI'     { & $Python cli_demo.py --help; break }
}

