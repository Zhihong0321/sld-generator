# SLD Generator - one-line installer for Windows
#
#   irm https://raw.githubusercontent.com/Zhihong0321/sld-generator/main/install.ps1 | iex
#
# Downloads (or updates) the repo, installs the `sldgen` command, and runs a health check.
# Re-run any time to update. Set $env:SLD_HOME first to choose the folder
# (default: $HOME\sld-generator). Your projects/ and library/ are never overwritten.

& {
    $ErrorActionPreference = "Stop"
    $Repo = "https://github.com/Zhihong0321/sld-generator"
    $Dir = if ($env:SLD_HOME) { $env:SLD_HOME } else { Join-Path $HOME "sld-generator" }

    Write-Host "SLD Generator installer" -ForegroundColor Cyan
    Write-Host "  folder: $Dir"

    # 1. Python 3.10+
    $py = $null
    foreach ($cand in @(@("py", "-3"), @("python"), @("python3"))) {
        try {
            $exe, $pre = $cand[0], @($cand | Select-Object -Skip 1)
            $ok = & $exe @pre -c "import sys; print(sys.version_info >= (3, 10))" 2>$null
            if ($ok -eq "True") { $py = $cand; break }
        } catch { }
    }
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

    Write-Host ""
    Write-Host "Installed in $Dir" -ForegroundColor Green
    Write-Host "Next:"
    Write-Host "  cd `"$Dir`""
    Write-Host "  Open this folder in your AI agent (Claude Code, Codex, Cursor, ...) and ask:"
    Write-Host "    'Follow AGENTS.md: generate an SLD for <your job>'"
    Write-Host "  Or by hand: sldgen library | sldgen init | sldgen check | sldgen build   (see docs/GUIDE.md)"
    Write-Host "  If 'sldgen' is not found, use: python -m sldgen ..."
}
