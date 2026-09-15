$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe') -or -not (Test-Path -LiteralPath 'node_modules/vite')) {
    throw 'Run setup.ps1 first.'
}
foreach ($port in @(8000, 5173)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
        throw "Port $port is already in use. Stop the existing service before running this launcher."
    }
}
# The operator requested separate visible service windows.
foreach ($script in @('start-backend.ps1', 'start-frontend.ps1')) {
    $scriptPath = Join-Path $PSScriptRoot "scripts/$script"
    Start-Process powershell.exe -WorkingDirectory $PSScriptRoot -WindowStyle Normal -ArgumentList @(
        '-NoProfile', '-NoExit', '-ExecutionPolicy', 'Bypass', '-File', "`"$scriptPath`""
    ) | Out-Null
}
Write-Host 'Backend: http://localhost:8000'
Write-Host 'WebApp: http://localhost:5173'
Write-Host 'Use Start Agent in the WebApp. Close each service window to exit.'
