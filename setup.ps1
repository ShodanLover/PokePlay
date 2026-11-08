# PokePlay one-click setup for Windows 10/11.
# Run it by double-clicking setup.bat (it calls this script).
# Installs Python, mGBA, Ollama and OBS with winget, downloads the AI model and creates config.toml.

$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot

function Step($text) { Write-Host ""; Write-Host "==> $text" -ForegroundColor Cyan }
function Ok($text)   { Write-Host "    OK: $text" -ForegroundColor Green }
function Warn($text) { Write-Host "    !! $text" -ForegroundColor Yellow }

function Refresh-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path", "User")
}

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Warn "winget (Windows Package Manager) was not found."
    Warn "Install 'App Installer' from the Microsoft Store, then run setup.bat again."
    exit 1
}

$apps = @(
    @{ Id = "Python.Python.3.12";   Name = "Python 3.12"; Url = "https://www.python.org/downloads/" },
    @{ Id = "JeffreyPfau.mGBA";     Name = "mGBA";        Url = "https://mgba.io/downloads.html" },
    @{ Id = "Ollama.Ollama";        Name = "Ollama";      Url = "https://ollama.com/download" },
    @{ Id = "OBSProject.OBSStudio"; Name = "OBS Studio";  Url = "https://obsproject.com/" }
)

$failed = @()
foreach ($app in $apps) {
    Step "Installing $($app.Name)"
    winget list --id $app.Id -e --accept-source-agreements *> $null
    if ($LASTEXITCODE -eq 0) { Ok "$($app.Name) is already installed"; continue }
    winget install --id $app.Id -e --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -eq 0) { Ok "$($app.Name) installed" }
    else { Warn "Could not install $($app.Name) automatically. Get it from $($app.Url)"; $failed += $app.Name }
}
Refresh-Path

Step "Checking Python"
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python -and (& python --version 2>&1) -match "Python 3\.(1[1-9])") { Ok (& python --version) }
else { Warn "Python 3.11+ not found on PATH yet. Restart your PC and run setup.bat again."; $failed += "Python" }

Step "Downloading the AI model (about 2.5 GB, this can take a while)"
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    $guess = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (Test-Path $guess) { $ollama = $guess }
}
if ($ollama) {
    # Make sure the Ollama server is running.
    try { Invoke-RestMethod http://127.0.0.1:11434/api/tags -TimeoutSec 3 | Out-Null }
    catch { Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden; Start-Sleep -Seconds 5 }
    & $ollama pull qwen3:4b
    if ($LASTEXITCODE -eq 0) { Ok "Model qwen3:4b ready" } else { Warn "Model download failed. Run: ollama pull qwen3:4b"; $failed += "AI model" }
} else { Warn "Ollama not found. Restart your PC and run setup.bat again."; $failed += "AI model" }

Step "Creating config.toml"
if (Test-Path config.toml) { Ok "config.toml already exists (left unchanged)" }
else {
    Copy-Item config.example.toml config.toml
    Ok "config.toml created (she'll pick her own name the first time she starts)"
}

Step "Turning off 'Pause when inactive' in mGBA"
$mgbaCfgDir = Join-Path $env:APPDATA "mGBA"
$mgbaCfg = Join-Path $mgbaCfgDir "config.ini"
New-Item -ItemType Directory -Force -Path $mgbaCfgDir | Out-Null
if (-not (Test-Path $mgbaCfg)) { Set-Content $mgbaCfg "[ports.qt]`r`npauseOnFocusLost=0`r`n" -Encoding ASCII; Ok "done" }
else {
    $ini = Get-Content $mgbaCfg -Raw
    if ($ini -match "pauseOnFocusLost=") { $ini = $ini -replace "pauseOnFocusLost=\d", "pauseOnFocusLost=0" }
    elseif ($ini -match "\[ports\.qt\]") { $ini = $ini -replace "\[ports\.qt\]", "[ports.qt]`r`npauseOnFocusLost=0" }
    else { $ini += "`r`n[ports.qt]`r`npauseOnFocusLost=0`r`n" }
    Set-Content $mgbaCfg $ini -Encoding ASCII
    Ok "done (double-check in mGBA: Tools > Settings)"
}

Write-Host ""
if ($failed.Count -eq 0) {
    Write-Host "All set! Next: open mGBA, load your FireRed ROM (start a NEW GAME or leave it on the title screen)," -ForegroundColor Green
    Write-Host "then Tools > Scripting > File > Load script" -ForegroundColor Green
    Write-Host "and pick lua\pokeplay_bridge.lua from this folder. Then double-click start.bat." -ForegroundColor Green
} else {
    Write-Host "Setup finished with some problems: $($failed -join ', ')" -ForegroundColor Yellow
    Write-Host "Fix those (see messages above), then run setup.bat again - it skips what's already done." -ForegroundColor Yellow
}
