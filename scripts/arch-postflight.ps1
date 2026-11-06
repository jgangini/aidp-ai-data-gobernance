$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    $failures = @()
    & .venv/Scripts/python.exe scripts/sentrux_scope.py
    if ($LASTEXITCODE -ne 0) { $failures += 'Architecture regression gate failed' }
    if (Test-Path '.sentrux/rules.toml') { & sentrux check .; if ($LASTEXITCODE -ne 0) { $failures += 'Architecture rules failed' } }
    else { Write-Host 'No custom Sentrux rules configured.' }
    $tempPath = '.local/pytest-' + [guid]::NewGuid().ToString('N')
    & .venv/Scripts/python.exe -m pytest tests -q --tb=short --basetemp $tempPath
    if ($LASTEXITCODE -ne 0) { $failures += 'Regression tests failed' }
    & .venv/Scripts/python.exe -m compileall -q src
    if ($LASTEXITCODE -ne 0) { $failures += 'Python compilation failed' }
    if ($failures.Count) { throw ($failures -join '; ') }
} finally { Pop-Location }
