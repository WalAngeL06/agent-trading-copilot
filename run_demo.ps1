$ErrorActionPreference = "Stop"

Write-Host "========================================="
Write-Host "Agent Trading Copilot - Demo Launcher"
Write-Host "========================================="

$envVars = @(
    "TELEGRAM_BOT_TOKEN",
    "WEBAPP_URL",
    "VITE_BACKEND_URL",
    "ALLOWED_ORIGINS",
    "OKX_API_KEY",
    "OKX_SECRET_KEY",
    "OKX_PASSPHRASE"
)

Write-Host "`n[1] Environment Validation"
foreach ($var in $envVars) {
    $val = [Environment]::GetEnvironmentVariable($var)
    if (-not $val) { $val = (Get-Content .env -ErrorAction SilentlyContinue | Select-String "^$var=(.*)$").Matches.Groups[1].Value }
    
    if ($val) {
        Write-Host "${var}: PRESENT" -ForegroundColor Green
    } else {
        Write-Host "${var}: MISSING" -ForegroundColor Yellow
    }
}

Write-Host "`n[2] Public URL Requirements"
Write-Host "For the Telegram WebApp to work on mobile, you MUST expose the frontend via HTTPS."
Write-Host "Options:"
Write-Host "  A) Cloudflare Tunnel: cloudflared tunnel --url http://localhost:5173"
Write-Host "  B) Ngrok: ngrok http 5173"
Write-Host "Set WEBAPP_URL in .env to the generated HTTPS url."
Write-Host "A physical phone also needs a SECOND HTTPS tunnel for the backend on port 8000."
Write-Host "Set VITE_BACKEND_URL to that backend tunnel URL."
Write-Host "Set ALLOWED_ORIGINS to the frontend origin (scheme + host, no path)."
Write-Host "The frontend does not proxy API requests, so one frontend tunnel is not enough."

Write-Host "`n[3] Starting Services"
Write-Host "Start Backend in a separate terminal:"
Write-Host "  .\.venv\Scripts\uvicorn.exe agent_trading.api:create_app --factory --port 8000"
Write-Host "`nStart Frontend in a separate terminal:"
Write-Host "  npm run dev"

Write-Host "`n[4] Health & Readiness"
Write-Host "Check backend readiness at: http://localhost:8000/health/ready"

Write-Host "`n[5] Telegram Bot"
Write-Host "Once the backend is started, send /start to your bot in Telegram."
Write-Host "Even if the trading engine is STOPPED, /start and /status will work."

Write-Host "`nSetup complete! Start your servers to begin."
