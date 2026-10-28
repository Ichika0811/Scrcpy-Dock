param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
    Write-Host "Using Python: $Python" -ForegroundColor Cyan
    Remove-Item -LiteralPath "$root\build\pyinstaller" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath "$root\build\ScrcpyDock.spec" -Force -ErrorAction SilentlyContinue
    & $Python -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --onedir `
        --noupx `
        --name ScrcpyDock `
        --icon "$root\assets\icon.ico" `
        --add-data "$root\assets;assets" `
        --version-file "$root\packaging\version_info.txt" `
        --distpath "$root\release" `
        --workpath "$root\build\pyinstaller" `
        --specpath "$root\build" `
        "$root\run.py"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
    Copy-Item -LiteralPath "$root\README.md" -Destination "$root\release\ScrcpyDock\README.md" -Force
    Copy-Item -LiteralPath "$root\docs" -Destination "$root\release\ScrcpyDock\docs" -Recurse -Force
    Write-Host ""
    Write-Host "Build complete:" -ForegroundColor Green
    Write-Host "  $root\release\ScrcpyDock\ScrcpyDock.exe"
} finally {
    Pop-Location
}
