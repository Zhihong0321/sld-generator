# SLD Generator - one-line installer for Windows
#
#   irm https://raw.githubusercontent.com/Zhihong0321/sld-generator/main/install.ps1 | iex
#
# Downloads (or updates) the repo, installs the `sldgen` command and the SLD Studio desktop
# app (Desktop + Start Menu shortcut), and runs a health check. Re-run any time to update.
# Set $env:SLD_HOME first to choose the folder (default: $HOME\sld-generator).
# Your projects/ and library/ are never overwritten.

& {
    $ErrorActionPreference = "Stop"
    $Repo = "https://github.com/Zhihong0321/sld-generator"
    $Dir = if ($env:SLD_HOME) { $env:SLD_HOME } else { Join-Path $HOME "sld-generator" }

    Write-Host "SLD Generator installer" -ForegroundColor Cyan
    Write-Host "  folder: $Dir"

    function Update-PathFromRegistry {
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                    [Environment]::GetEnvironmentVariable("Path", "User")
    }
    function Install-WithWinget($id, $label) {
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { return $false }
        Write-Host "  $label not found - installing it with winget (this can take a few minutes)..."
        winget install --id $id -e --silent --accept-source-agreements --accept-package-agreements | Out-Host
        Update-PathFromRegistry
        return $true
    }

    # 1. Python 3.10+
    $py = $null
    $findPy = {
    foreach ($cand in @(@("py", "-3"), @("python"), @("python3"))) {
        try {
            $exe, $pre = $cand[0], @($cand | Select-Object -Skip 1)
            $ok = & $exe @pre -c "import sys; print(sys.version_info >= (3, 10))" 2>$null
            if ($ok -eq "True") { return ,$cand }
        } catch { }
    }
    }
    $py = & $findPy
    if (-not $py -and (Install-WithWinget "Python.Python.3.12" "Python")) { $py = & $findPy }
    if (-not $py) {
        Write-Host "Python 3.10+ not found. Install it, then re-run this command:" -ForegroundColor Red
        Write-Host "  winget install Python.Python.3.12"
        return
    }
    $pyExe, $pyPre = $py[0], @($py | Select-Object -Skip 1)
    Write-Host "  python: $(& $pyExe @pyPre --version)"

    # 2. Get or update the code
    $hasGit = [bool](Get-Command git -ErrorAction SilentlyContinue)
    if ($hasGit -and (Test-Path (Join-Path $Dir ".git"))) {
        Write-Host "Updating existing copy (git pull)..."
        git -C $Dir pull --ff-only
    } elseif ($hasGit -and -not (Test-Path $Dir)) {
        Write-Host "Cloning $Repo ..."
        git clone --depth 1 $Repo $Dir
    } else {
        Write-Host "Downloading zip..."
        $tmp = Join-Path ([IO.Path]::GetTempPath()) ("sldgen-" + [guid]::NewGuid())
        New-Item -ItemType Directory -Path $tmp | Out-Null
        $zip = Join-Path $tmp "src.zip"
        Invoke-WebRequest "$Repo/archive/refs/heads/main.zip" -OutFile $zip -UseBasicParsing
        Expand-Archive $zip -DestinationPath $tmp
        $src = Get-ChildItem $tmp -Directory | Select-Object -First 1
        New-Item -ItemType Directory -Force -Path $Dir | Out-Null
        foreach ($item in Get-ChildItem $src.FullName -Force) {
            $target = Join-Path $Dir $item.Name
            if ($item.Name -in @("projects", "library") -and (Test-Path $target)) { continue }  # keep user data
            Copy-Item $item.FullName $target -Recurse -Force
        }
        Remove-Item $tmp -Recurse -Force
    }

    # 3. Install the sldgen command
    Write-Host "Installing the sldgen command..."
    & $pyExe @pyPre -m pip install --quiet --disable-pip-version-check -e $Dir
    if ($LASTEXITCODE -ne 0) { Write-Host "pip install failed." -ForegroundColor Red; return }

    # 4. Health check
    Push-Location $Dir
    try { & $pyExe @pyPre -m sldgen doctor } finally { Pop-Location }

    # 5. SLD Studio desktop app (needs Node.js for its one-time npm install)
    $appDir = Join-Path $Dir "app"
    $appOk = $false
    if (Test-Path (Join-Path $appDir "package.json")) {
        if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Install-WithWinget "OpenJS.NodeJS.LTS" "Node.js" | Out-Null }
        if (Get-Command npm -ErrorAction SilentlyContinue) {
            Write-Host "Installing the SLD Studio desktop app..."
            Push-Location $appDir
            try { npm install --no-audit --no-fund --loglevel=error | Out-Host } finally { Pop-Location }
            $electron = Join-Path $appDir "node_modules\electron\dist\electron.exe"
            $electronInstall = Join-Path $appDir "node_modules\electron\install.js"
            if (-not (Test-Path $electron) -and (Test-Path $electronInstall)) {
                Write-Host "Downloading the Electron runtime..."
                Push-Location (Split-Path $electronInstall)
                try { node install.js | Out-Host } finally { Pop-Location }
            }
            if (Test-Path $electron) {
                $shell = New-Object -ComObject WScript.Shell
                $startMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "SLD Studio.lnk"
                $desktop = Join-Path ([Environment]::GetFolderPath("Desktop")) "SLD Studio.lnk"
                foreach ($lnkPath in @($desktop, $startMenu)) {
                    $lnk = $shell.CreateShortcut($lnkPath)
                    $lnk.TargetPath = $electron
                    $lnk.Arguments = "`"$appDir`""
                    $lnk.WorkingDirectory = $appDir
                    $appIcon = Join-Path $appDir "assets\icon.ico"
                    $lnk.IconLocation = if (Test-Path $appIcon) { "$appIcon,0" } else { "$electron,0" }
                    $lnk.Description = "SLD Studio - Solar ATAP SLD generator"
                    $lnk.Save()
                }
                $appOk = $true
            } else {
                Write-Host "The desktop app did not install (npm install problem). The sldgen command still works." -ForegroundColor Yellow
            }
        } else {
            Write-Host "Node.js not found, so the desktop app was skipped. Install Node.js LTS from https://nodejs.org and run this installer again." -ForegroundColor Yellow
        }
    }

    Write-Host ""
    Write-Host "Installed in $Dir" -ForegroundColor Green
    if ($appOk) {
        Write-Host "SLD Studio: open it from the Desktop or Start Menu shortcut 'SLD Studio'." -ForegroundColor Green
        Write-Host "  It updates itself from GitHub. For the AI fill, add your API key under Settings."
        Start-Process -FilePath $electron -ArgumentList "`"$appDir`"" -WorkingDirectory $appDir
    }
    Write-Host "Command line / AI agents:"
    Write-Host "  cd `"$Dir`""
    Write-Host "  Open this folder in your AI agent (Claude Code, Codex, Cursor, ...) and ask:"
    Write-Host "    'Follow AGENTS.md: generate an SLD for <your job>'"
    Write-Host "  Or by hand: sldgen library | sldgen init | sldgen check | sldgen build   (see docs/GUIDE.md)"
    Write-Host "  If 'sldgen' is not found, use: python -m sldgen ..."
}
