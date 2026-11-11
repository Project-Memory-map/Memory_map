param([switch]$Apply)

$ErrorActionPreference = 'Stop'

Set-Location (Split-Path $PSScriptRoot -Parent)

$python = Join-Path (Get-Location) '.venv\Scripts\python.exe'

if (!(Test-Path $python)) {
    throw 'Không tìm thấy .venv\Scripts\python.exe'
}

if ($Apply) {
    & $python -m app.modules.memories.cleanup_media --apply
} else {
    & $python -m app.modules.memories.cleanup_media
}

exit $LASTEXITCODE