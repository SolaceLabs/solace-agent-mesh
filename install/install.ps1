# Copyright Solace Corporation
# SPDX-License-Identifier: BUSL-1.1

# Install Agent Mesh Desktop Application (Solace Agent Mesh) on Windows, from the
# latest GitHub release.
#
#   irm https://raw.githubusercontent.com/SolaceProducts/solace-agent-mesh/main/install/install.ps1 | iex
#
# Per-user install (no administrator rights) to %LOCALAPPDATA%\Programs\Solace Agent Mesh.
# The download is checked against the SHA-256 digest that GitHub publishes for the
# release asset, the installer's Authenticode signature is verified before it
# runs, and the sam CLI folder is added to your user PATH unless SAM_INSTALL_NO_PATH=1.
# Set SAM_INSTALL_DRY_RUN=1 to print what would happen without downloading, or
# SAM_INSTALL_DOWNLOAD_ONLY=1 to download and verify the release asset without installing.
# SAM_INSTALL_REPO selects the GitHub repository (owner/name) to install from.
# GITHUB_TOKEN or GH_TOKEN, if set, is used to read a private repository.

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

$Repo = if ($env:SAM_INSTALL_REPO) { $env:SAM_INSTALL_REPO } else { 'SolaceProducts/solace-agent-mesh' }
$Token = if ($env:GITHUB_TOKEN) { $env:GITHUB_TOKEN } elseif ($env:GH_TOKEN) { $env:GH_TOKEN } else { $null }
$AssetSuffix = '-desktop-free-windows-x64.zip'
$InstallDir = Join-Path $env:LOCALAPPDATA 'Programs\Solace Agent Mesh'
$CliDir = Join-Path $InstallDir 'cli'
$ExpectedSigner = 'Solace'

if (-not [Environment]::Is64BitOperatingSystem) {
    throw 'Agent Mesh Desktop Application requires 64-bit Windows 10 or later.'
}
if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
    Write-Warning 'No native ARM64 build exists; the x64 build will run under Windows emulation.'
}

$ApiHeaders = @{ Accept = 'application/vnd.github+json'; 'User-Agent' = 'sam-install' }
if ($Token) { $ApiHeaders.Authorization = "Bearer $Token" }
try {
    $Release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" -Headers $ApiHeaders -UseBasicParsing
}
catch {
    throw "Could not read the latest release of $Repo (for a private repository, set GITHUB_TOKEN): $($_.Exception.Message)"
}
$Asset = $Release.assets | Where-Object { $_.name.EndsWith($AssetSuffix) } | Select-Object -First 1
if (-not $Asset) { throw "The latest release of $Repo has no asset ending in $AssetSuffix." }
$ExpectedSha256 = if ($Asset.digest -and $Asset.digest.StartsWith('sha256:')) { $Asset.digest.Substring(7).ToLowerInvariant() } else { $null }

if ($env:SAM_INSTALL_DRY_RUN -eq '1') {
    Write-Host "Would download: $($Asset.browser_download_url)"
    Write-Host "Would verify:   SHA-256 $(if ($ExpectedSha256) { $ExpectedSha256 } else { '(not published)' })"
    Write-Host "Would install:  $InstallDir (silent, per-user)"
    if ($env:SAM_INSTALL_NO_PATH -ne '1') { Write-Host "Would add to user PATH: $CliDir" }
    return
}

$Work = Join-Path ([IO.Path]::GetTempPath()) "sam-desktop-setup-$([guid]::NewGuid())"
New-Item -ItemType Directory -Path $Work | Out-Null
try {
    $Zip = Join-Path $Work $Asset.name
    Write-Host "Downloading $($Asset.name) ..."
    if ($Token) {
        $DownloadHeaders = @{ Accept = 'application/octet-stream'; Authorization = "Bearer $Token"; 'User-Agent' = 'sam-install' }
        Invoke-WebRequest -Uri $Asset.url -Headers $DownloadHeaders -OutFile $Zip -UseBasicParsing
    }
    else {
        Invoke-WebRequest -Uri $Asset.browser_download_url -OutFile $Zip -UseBasicParsing
    }

    if ($ExpectedSha256) {
        $ActualSha256 = (Get-FileHash -Path $Zip -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($ActualSha256 -ne $ExpectedSha256) { throw "SHA-256 of $($Asset.name) does not match the release; not installing." }
        Write-Host "Verified SHA-256 $ActualSha256"
    }
    else {
        Write-Warning 'The release does not publish a SHA-256 digest; checking the size only.'
        if ((Get-Item $Zip).Length -ne $Asset.size) { throw "Downloaded size of $($Asset.name) does not match the release." }
    }

    if ($env:SAM_INSTALL_DOWNLOAD_ONLY -eq '1') {
        Move-Item -Path $Zip -Destination (Join-Path (Get-Location) $Asset.name) -Force
        Write-Host "Saved $($Asset.name)"
        return
    }

    Expand-Archive -Path $Zip -DestinationPath $Work -Force
    $Installer = Get-ChildItem -Path $Work -Filter '*.exe' | Select-Object -First 1
    if (-not $Installer) { throw "$($Asset.name) does not contain an installer." }

    $sig = Get-AuthenticodeSignature -FilePath $Installer.FullName
    if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch $ExpectedSigner) {
        throw "Installer signature check failed (status: $($sig.Status)); not installing."
    }

    Write-Host 'Installing ...'
    $proc = Start-Process -FilePath $Installer.FullName -ArgumentList '/S' -Wait -PassThru
    if ($proc.ExitCode -ne 0) { throw "Installer exited with code $($proc.ExitCode)." }
}
finally {
    Remove-Item -Path $Work -Recurse -Force -ErrorAction SilentlyContinue
}

if ($env:SAM_INSTALL_NO_PATH -ne '1' -and (Test-Path (Join-Path $CliDir 'sam.exe'))) {
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    if (($userPath -split ';') -notcontains $CliDir) {
        [Environment]::SetEnvironmentVariable('Path', (@($userPath, $CliDir) | Where-Object { $_ }) -join ';', 'User')
        Write-Host "Added $CliDir to your user PATH (open a new terminal to use 'sam')."
    }
}

Write-Host ''
Write-Host 'Installed Agent Mesh Desktop Application. Launch "Solace Agent Mesh" from the Start menu.'
Write-Host 'Agent Mesh Desktop Application uses Microsoft Edge WebView2, which Windows 10 and 11 normally include.'
