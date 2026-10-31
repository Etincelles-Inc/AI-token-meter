$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path -LiteralPath ".build-venv/Scripts/python.exe")) {
    python -m venv .build-venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create build environment" }
}
& ".build-venv/Scripts/python.exe" -m pip install -r tools/build-requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Build dependencies failed" }
& ".build-venv/Scripts/python.exe" -m unittest discover -s tests -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed" }
& ".build-venv/Scripts/python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name EtincellesTokenMeter --exclude-module gi --exclude-module cairo --exclude-module token_speedometer.gtk_gui launcher.py
if ($LASTEXITCODE -ne 0) { throw "Executable build failed" }
Write-Output "Built dist/EtincellesTokenMeter.exe"
