# Demo script for WIDERSPRUCH.JETZT API (PowerShell)
# Prerequisites: API running on :8008, Chroma index present, Ollama optional for generation.

$Base = $env:APP_URL
if (-not $Base) { $Base = "http://127.0.0.1:8008" }

Write-Host "== Health ==" -ForegroundColor Cyan
Invoke-RestMethod "$Base/health" | ConvertTo-Json -Depth 5

Write-Host "`n== RAG search ==" -ForegroundColor Cyan
try {
  Invoke-RestMethod "$Base/search?q=Akteneinsicht&k=3" | ConvertTo-Json -Depth 4
} catch {
  Write-Host "Search failed (is the Chroma index built?): $_" -ForegroundColor Yellow
}

Write-Host "`n== Preview workflow (needs Ollama + index + may 402 if no credits for download) ==" -ForegroundColor Cyan
$body = Get-Content -Raw "samples/api_request_example.json"
try {
  Invoke-RestMethod -Method Post -Uri "$Base/widerspruch/workflow?preview=1" `
    -ContentType "application/json; charset=utf-8" -Body $body
} catch {
  Write-Host "Preview failed: $_" -ForegroundColor Yellow
}

Write-Host "`nOpen UI: $Base/ui/" -ForegroundColor Green
