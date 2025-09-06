param(
    [ValidateSet('Install','Test','Demo','GUI','Labels','CLI','GUIFix','PSG')]
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
  'GUIFix'  { & $Python scripts/reinstall_pysimplegui.py; break }
  'PSG'     {
      & $Python -m pip uninstall -y PySimpleGUI;
      & $Python -m pip cache purge;
      & $Python -m pip install --force-reinstall --extra-index-url https://PySimpleGUI.net/install PySimpleGUI;
      break
  }
}
