$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw 'Install Python 3.11 or newer (with the Windows py launcher).' }
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'Install Node.js 22.12 or newer.' }
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    & py -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python environment setup failed.' }
}
& ./.venv/Scripts/python.exe -m pip install -e '.[product,test-product]'
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
& npm.cmd ci
if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
& npm.cmd install --global '@okx_ai/okx-trade-mcp@1.4.6'
if ($LASTEXITCODE -ne 0) { throw 'OKX ATK installation failed.' }
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
Write-Host 'Ready. Optional credentials go in .env. Start with .\run.ps1.'
