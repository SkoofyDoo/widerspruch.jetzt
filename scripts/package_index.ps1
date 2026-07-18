# Package local Chroma index for deploy (run where data/chroma exists).
# Creates dist/chroma-index.zip — upload as release asset or copy to server.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$chroma = Join-Path $root "data\chroma"
$outDir = Join-Path $root "dist"
$outZip = Join-Path $outDir "chroma-index.zip"

if (-not (Test-Path $chroma)) {
  Write-Error "Missing data/chroma. Build index first: python src/index.py (after fetch/clean/chunk)."
}

New-Item -ItemType Directory -Force -Path $outDir | Out-Null
if (Test-Path $outZip) { Remove-Item -Force $outZip }

Compress-Archive -Path (Join-Path $chroma "*") -DestinationPath $outZip -Force
Write-Host "Wrote $outZip"
Write-Host "On server: expand into data/chroma/"
