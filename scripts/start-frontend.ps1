$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& npm.cmd run dev
if ($LASTEXITCODE -ne 0) { throw 'WebApp stopped with an error.' }
