$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& ./.venv/Scripts/python.exe -B -m uvicorn agent_trading.api:create_app --factory --host 127.0.0.1 --port 8000
if ($LASTEXITCODE -ne 0) { throw 'Backend stopped with an error.' }
