$ErrorActionPreference = 'Stop'

$repo = (Resolve-Path '..').Path
$markerStart = '# >>> Knot-Labs venv auto-activate >>>'
$markerEnd   = '# <<< Knot-Labs venv auto-activate <<<'
$snippet = @"
$markerStart
# Auto-activate .venv when starting in or cd-ing to this repo
# Repo: $repo
function global:__KnotLabs-ActivateVenv {
  try {
    $root = "$repo"
    $here = (Get-Location).Path
    if ($here -like ($root + '*')) {
      $venvRoot = Join-Path $root '.venv'
      $activate = Join-Path $venvRoot 'Scripts/Activate.ps1'
      if (Test-Path $activate) {
        if (-not $env:VIRTUAL_ENV -or ($env:VIRTUAL_ENV -ne $venvRoot)) {
          . $activate | Out-Null
        }
      }
    }
  } catch {}
}
# Wrap the existing prompt to trigger auto-activation on each prompt render
if (-not (Test-Path function:__KnotLabs-OriginalPrompt)) {
  if (Test-Path function:prompt) { Copy-Item function:prompt function:__KnotLabs-OriginalPrompt }
  function global:prompt {
    __KnotLabs-ActivateVenv
    if (Test-Path function:__KnotLabs-OriginalPrompt) { & __KnotLabs-OriginalPrompt } else { 'PS ' + (Get-Location) + '> ' }
  }
}
$markerEnd
"@

$profiles = @(
  (Join-Path $HOME 'Documents/PowerShell/Microsoft.PowerShell_profile.ps1'),
  (Join-Path $HOME 'Documents/WindowsPowerShell/Microsoft.PowerShell_profile.ps1'),
  (Join-Path $HOME 'OneDrive/Documents/PowerShell/Microsoft.PowerShell_profile.ps1'),
  (Join-Path $HOME 'OneDrive/Documents/WindowsPowerShell/Microsoft.PowerShell_profile.ps1')
)

foreach ($full in $profiles) {
  try {
    $dir = Split-Path -Parent $full
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $content = ''
    if (Test-Path $full) { $content = Get-Content $full -Raw }
    if ($content -match [regex]::Escape($markerStart) -and $content -match [regex]::Escape($markerEnd)) {
      $pattern = "(?s)" + [regex]::Escape($markerStart) + ".*?" + [regex]::Escape($markerEnd)
      $content = [regex]::Replace($content, $pattern, $snippet)
    } else {
      if ($content -and -not $content.EndsWith("`n")) { $content += "`n" }
      $content += $snippet
    }
    Set-Content -Path $full -Value $content -Encoding UTF8
  } catch {
    Write-Warning "Failed to update profile: $full - $($_.Exception.Message)"
  }
}

Write-Output 'Added venv auto-activate snippet to PowerShell profiles.'

