$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    & .venv/Scripts/python.exe scripts/sentrux_scope.py --save
    if ($LASTEXITCODE -ne 0) { throw 'Architecture baseline failed' }
    if (Test-Path '.sentrux/rules.toml') { & sentrux check .; if ($LASTEXITCODE -ne 0) { throw 'Architecture rules failed' } }
    else { Write-Host 'No custom Sentrux rules configured.' }
} finally { Pop-Location }
