param([string]$ISCC = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe")
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Push-Location $projectRoot
try {
    $uv = if (Get-Command uv -ErrorAction SilentlyContinue) { 'uv' } else { Join-Path $projectRoot '.tools\uv\uv.exe' }
    if (-not (Test-Path -LiteralPath $ISCC)) { throw 'Install Inno Setup 6 or pass -ISCC with the compiler path.' }
    & $uv sync --locked --extra desktop --group packaging
    if ($LASTEXITCODE) { throw 'Python dependency installation failed. Close running development instances and retry.' }
    & npm.cmd ci --prefix byod/ui
    if ($LASTEXITCODE) { throw 'Frontend dependency installation failed.' }
    & npm.cmd run build --prefix byod/ui
    if ($LASTEXITCODE) { throw 'Frontend build failed.' }
    $bootstrapper = Join-Path $projectRoot '.tools\MicrosoftEdgeWebview2Setup.exe'
    if (-not (Test-Path -LiteralPath $bootstrapper)) {
        New-Item -ItemType Directory -Path .tools -Force | Out-Null
        Invoke-WebRequest -UseBasicParsing -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $bootstrapper
    }
    $signature = Get-AuthenticodeSignature -LiteralPath $bootstrapper
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') {
        throw 'WebView2 bootstrapper signature verification failed.'
    }
    & .venv\Scripts\python.exe -m PyInstaller --noconfirm --workpath build/windows packaging/BYOD.spec
    if ($LASTEXITCODE) { throw 'Desktop application build failed.' }
    & $ISCC packaging/BYOD.iss
    if ($LASTEXITCODE) { throw 'Installer build failed.' }
    Get-FileHash dist/installers/BYOD-Setup-0.1.0-x64.exe -Algorithm SHA256
} finally { Pop-Location }
