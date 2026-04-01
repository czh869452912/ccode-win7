[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('doctor', 'deps', 'assemble', 'verify', 'release')]
    [string]$Command = 'release',

    [ValidateSet('dev', 'release')]
    [string]$Profile = '',

    [string]$Config = 'scripts/package.config.json',
    [string]$BundleRoot = '',
    [string]$OutputRoot = '',
    [string]$ArtifactName = '',
    [switch]$AllowDownload,
    [switch]$NoZip,
    [switch]$Strict,
    [switch]$Json
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'package-lib.ps1')

$report = $null

try {
    if ($Command -ne 'doctor') {
        throw "Not implemented yet: $Command"
    }

    $projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
    $configPath = Resolve-ConfigPath -ProjectRoot $projectRoot -Path $Config
    $configObject = Read-PackageConfig -Path $configPath
    $context = New-PackageContext `
        -ProjectRoot $projectRoot `
        -Config $configObject `
        -ConfigPath $configPath `
        -Command $Command `
        -RequestedProfile $Profile `
        -BundleRoot $BundleRoot `
        -OutputRoot $OutputRoot `
        -ArtifactName $ArtifactName `
        -AllowDownload ([bool]$AllowDownload) `
        -NoZip ([bool]$NoZip) `
        -Strict ([bool]$Strict)

    $report = Invoke-PackageDoctor -Context $context
}
catch {
    $errorMessage = $_.Exception.Message
    if (-not $report) {
        $report = [ordered]@{
            command = $Command
            profile = $Profile
            command_status = 'NOT_READY'
            final_status = $null
            blocking_issues = @($errorMessage)
        }
    }
    else {
        $report.command_status = 'NOT_READY'
        $report.final_status = $null
        if (-not $report.blocking_issues) {
            $report.blocking_issues = @()
        }
        $report.blocking_issues += $errorMessage
    }

    if ($Json) {
        $report | ConvertTo-Json -Depth 8
    }
    else {
        Write-Error -Message $errorMessage
    }
    exit 1
}

if ($Json) {
    $report | ConvertTo-Json -Depth 8
}

exit (Get-PackageExitCode -Report $report)
