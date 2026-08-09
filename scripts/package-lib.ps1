Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Write-PackageLog {
    param([string]$Message)
    if (-not $Global:PackageJsonMode) {
        Write-Host $Message
    }
}

function Resolve-ConfigPath {
    param(
        [string]$ProjectRoot,
        [string]$Path
    )

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }
    return Join-Path $ProjectRoot $Path
}

function Copy-VerifiedPythonWheels {
    param(
        [string]$SourceRoot,
        [string]$DestinationRoot,
        [string[]]$WheelNames
    )

    if (-not (Test-Path -LiteralPath $SourceRoot -PathType Container)) {
        throw "Python wheel source directory not found: $SourceRoot"
    }
    if (@($WheelNames).Count -ne 6) {
        throw 'Exactly six verified Python wheel names are required.'
    }

    $sourceRootItem = Get-Item -LiteralPath $SourceRoot -Force
    if (($sourceRootItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Python wheel source directory must not be a reparse point: $SourceRoot"
    }
    $resolvedSourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
    $destinationFullPath = [System.IO.Path]::GetFullPath($DestinationRoot)
    if ($resolvedSourceRoot -eq $destinationFullPath) {
        throw 'Python wheel source and destination directories must differ.'
    }
    if (Test-Path -LiteralPath $DestinationRoot) {
        $destinationItem = Get-Item -LiteralPath $DestinationRoot -Force
        if (($destinationItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Python wheel destination must not be a reparse point: $DestinationRoot"
        }
    }

    $seen = @{}
    $validatedNames = @()
    $validatedSourcePaths = @()
    foreach ($wheelName in @($WheelNames)) {
        $name = [string]$wheelName
        if (-not $name -or [System.IO.Path]::GetFileName($name) -ne $name -or -not $name.EndsWith('.whl', [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Invalid verified Python wheel name: $name"
        }
        $caseKey = $name.ToUpperInvariant()
        if ($seen.ContainsKey($caseKey)) {
            throw "Duplicate verified Python wheel name: $name"
        }
        $seen[$caseKey] = $true

        $sourcePath = Join-Path $resolvedSourceRoot $name
        if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
            throw "Verified Python wheel not found: $name"
        }
        $sourceItem = Get-Item -LiteralPath $sourcePath -Force
        if (($sourceItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Verified Python wheel must not be a reparse point: $name"
        }
        $resolvedSourcePath = (Resolve-Path -LiteralPath $sourcePath).Path
        if ((Split-Path -Parent $resolvedSourcePath) -ne $resolvedSourceRoot) {
            throw "Verified Python wheel resolves outside source directory: $name"
        }
        $validatedNames += $name
        $validatedSourcePaths += $resolvedSourcePath
    }

    foreach ($validatedSourcePath in $validatedSourcePaths) {
        $sourceItem = Get-Item -LiteralPath $validatedSourcePath -Force
        if (($sourceItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Verified Python wheel became a reparse point before copy: $validatedSourcePath"
        }
        if ((Split-Path -Parent (Resolve-Path -LiteralPath $validatedSourcePath).Path) -ne $resolvedSourceRoot) {
            throw "Verified Python wheel resolves outside source directory before copy: $validatedSourcePath"
        }
    }

    if (Test-Path -LiteralPath $DestinationRoot) {
        Remove-Item -LiteralPath $DestinationRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $DestinationRoot -Force | Out-Null
    for ($index = 0; $index -lt $validatedNames.Count; $index++) {
        $name = $validatedNames[$index]
        Copy-Item -LiteralPath $validatedSourcePaths[$index] -Destination (Join-Path $DestinationRoot $name) -Force
    }
    return $validatedNames
}

function Publish-VerifiedPythonWheels {
    param(
        [string]$SourceRoot,
        [string]$DestinationRoot,
        [string[]]$WheelNames,
        [string]$PythonPath,
        [string]$CheckerPath
    )

    if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
        throw "Python executable not found for wheel publication: $PythonPath"
    }
    if (-not (Test-Path -LiteralPath $CheckerPath -PathType Leaf)) {
        throw "Python distribution checker not found: $CheckerPath"
    }

    $destinationFullPath = [System.IO.Path]::GetFullPath($DestinationRoot)
    $destinationParent = Split-Path -Parent $destinationFullPath
    if (-not (Test-Path -LiteralPath $destinationParent -PathType Container)) {
        New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null
    }
    $destinationParentItem = Get-Item -LiteralPath $destinationParent -Force
    if (($destinationParentItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Python wheel destination parent must not be a reparse point: $destinationParent"
    }
    if (Test-Path -LiteralPath $destinationFullPath) {
        $destinationItem = Get-Item -LiteralPath $destinationFullPath -Force
        if (($destinationItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Python wheel destination must not be a reparse point: $destinationFullPath"
        }
        foreach ($child in @(Get-ChildItem -LiteralPath $destinationFullPath -Force)) {
            if ($child.PSIsContainer -or (($child.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
                throw "Existing Python wheel destination contains an unsafe entry: $($child.Name)"
            }
        }
    }

    $destinationLeaf = Split-Path -Leaf $destinationFullPath
    $uniqueId = [System.Guid]::NewGuid().ToString('N')
    $tempRoot = Join-Path $destinationParent ('.' + $destinationLeaf + '.tmp.' + $uniqueId)
    $backupRoot = Join-Path $destinationParent ('.' + $destinationLeaf + '.backup.' + $uniqueId)
    $published = $false
    $backupCreated = $false
    try {
        $null = Copy-VerifiedPythonWheels `
            -SourceRoot $SourceRoot `
            -DestinationRoot $tempRoot `
            -WheelNames $WheelNames

        $tempItem = Get-Item -LiteralPath $tempRoot -Force
        if (($tempItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Temporary Python wheel directory must not be a reparse point: $tempRoot"
        }
        $checkerOutput = @(& $PythonPath $CheckerPath --dist-dir $tempRoot)
        if ($LASTEXITCODE -ne 0) {
            throw 'copied Python wheelhouse failed validation'
        }
        $checkerReport = ($checkerOutput -join "`n") | ConvertFrom-Json
        $verifiedNames = @($checkerReport.verified_wheels)
        if (-not $checkerReport.ok -or $verifiedNames.Count -ne 6) {
            throw 'copied Python wheelhouse failed validation'
        }
        for ($index = 0; $index -lt $verifiedNames.Count; $index++) {
            if (-not [string]::Equals([string]$verifiedNames[$index], [string]$WheelNames[$index], [System.StringComparison]::OrdinalIgnoreCase)) {
                throw 'copied Python wheelhouse verified a different wheel set'
            }
        }

        $tempItem = Get-Item -LiteralPath $tempRoot -Force
        if (($tempItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Temporary Python wheel directory must not be a reparse point: $tempRoot"
        }
        if (Test-Path -LiteralPath $destinationFullPath) {
            $destinationItem = Get-Item -LiteralPath $destinationFullPath -Force
            if (($destinationItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Python wheel destination must not be a reparse point: $destinationFullPath"
            }
            Move-Item -LiteralPath $destinationFullPath -Destination $backupRoot
            $backupCreated = $true
        }
        try {
            Move-Item -LiteralPath $tempRoot -Destination $destinationFullPath
            $published = $true
        }
        catch {
            if ($backupCreated -and -not (Test-Path -LiteralPath $destinationFullPath)) {
                Move-Item -LiteralPath $backupRoot -Destination $destinationFullPath
                $backupCreated = $false
            }
            throw
        }
        if ($backupCreated) {
            Remove-Item -LiteralPath $backupRoot -Recurse -Force
            $backupCreated = $false
        }
        return $verifiedNames
    }
    finally {
        if (-not $published -and (Test-Path -LiteralPath $tempRoot)) {
            $tempItem = Get-Item -LiteralPath $tempRoot -Force
            if (($tempItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -eq 0) {
                Remove-Item -LiteralPath $tempRoot -Recurse -Force
            }
        }
        if ($backupCreated -and -not (Test-Path -LiteralPath $destinationFullPath)) {
            Move-Item -LiteralPath $backupRoot -Destination $destinationFullPath
        }
    }
}

function Read-PackageConfig {
    param(
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Package config not found: $Path"
    }
    $raw = Get-Content -LiteralPath $Path -Raw
    $config = $raw | ConvertFrom-Json
    $configOrigin = [string]$config.metadata.config_origin
    if ($configOrigin -notin @('production', 'fixture')) {
        throw "Package config must define metadata.config_origin as production or fixture."
    }
    if (-not $config.profiles.dev -or -not $config.profiles.release) {
        throw "Package config must define both dev and release profiles."
    }
    return $config
}

function New-PackageReport {
    param(
        [string]$Command,
        [string]$Profile,
        [string]$Flavor = ''
    )

    return [ordered]@{
        command = $Command
        profile = $Profile
        flavor = $Flavor
        started_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        command_status = 'running'
        final_status = $null
        artifact_status = 'provisional'
        publishable = $false
        stages = @()
        blocking_issues = @()
        warnings = @()
    }
}

function New-PackageContextReport {
    param(
        [System.Collections.IDictionary]$Context
    )

    $runId = if ($Context.run_id) { [string]$Context.run_id } else { [guid]::NewGuid().ToString('N') }
    return [ordered]@{
        command = [string]$Context.command
        profile = [string]$Context.profile
        flavor = [string]$Context.flavor
        bundle_plan_path = [string]$Context.bundle_plan_path
        bundle_plan_sha256 = [string]$Context.bundle_plan_sha256
        run_id = $runId
        execution_kind = [string]$Context.execution_kind
        config_origin = [string]$Context.config_origin
        config_path = [string]$Context.config_path
        source_revision = [string]$Context.source_revision
        reports_root = [string]$Context.reports_root
        artifact_root = [string]$Context.artifact_root
        started_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        command_status = 'running'
        final_status = $null
        artifact_status = 'provisional'
        publishable = $false
        stages = @()
        blocking_issues = @()
        warnings = @()
    }
}

function Assert-BundlePlanArray {
    param(
        [object]$Plan,
        [string]$Name
    )

    if (-not ($Plan.PSObject.Properties.Name -contains $Name)) {
        throw "Bundle plan is missing required array: $Name"
    }
    $seen = @{}
    foreach ($item in @($Plan.$Name)) {
        $value = [string]$item
        if (-not $value) {
            throw "Bundle plan array contains an empty value: $Name"
        }
        if ($seen.ContainsKey($value)) {
            throw "Bundle plan array contains a duplicate value: $Name=$value"
        }
        $seen[$value] = $true
    }
}

function Assert-KnownBundlePlanIds {
    param(
        [string]$Name,
        [object[]]$Values,
        [object[]]$KnownValues
    )

    $known = @{}
    foreach ($item in @($KnownValues)) {
        $known[[string]$item] = $true
    }
    foreach ($item in @($Values)) {
        $value = [string]$item
        if (-not $known.ContainsKey($value)) {
            throw "Bundle plan contains unknown $Name id: $value"
        }
    }
}

function Assert-ExactBundlePlanIds {
    param(
        [string]$Name,
        [object[]]$Actual,
        [string[]]$Expected
    )

    if (@($Actual).Count -ne @($Expected).Count) {
        throw "Bundle plan must contain exactly $($Expected.Count) $Name ids."
    }
    for ($index = 0; $index -lt $Expected.Count; $index++) {
        if ([string]$Actual[$index] -ne $Expected[$index]) {
            throw "Bundle plan $Name ids do not match the required distribution order."
        }
    }
}

function Assert-SameBundlePlanIdSet {
    param(
        [string]$Name,
        [object[]]$Actual,
        [object[]]$Expected
    )

    $actualValues = @($Actual | ForEach-Object { [string]$_ } | Select-Object -Unique)
    $expectedValues = @($Expected | ForEach-Object { [string]$_ } | Select-Object -Unique)
    if ($actualValues.Count -ne $expectedValues.Count) {
        throw "Bundle plan $Name ids do not match the runtime contract closure."
    }
    foreach ($value in $expectedValues) {
        if (-not ($actualValues -contains $value)) {
            throw "Bundle plan $Name ids do not match the runtime contract closure."
        }
    }
}

function Read-VerifiedBundlePlan {
    param(
        [string]$ProjectRoot,
        [string]$BundlePlanPath,
        [string]$BundlePlanSha256,
        [string]$AssetManifestPath = 'scripts\offline-assets.json',
        [string]$RuntimeContractPath = 'scripts\offline-runtime-contract.json'
    )

    if (-not $BundlePlanPath) {
        throw 'BundlePlanPath is required.'
    }
    $resolvedPlanPath = if ([System.IO.Path]::IsPathRooted($BundlePlanPath)) {
        $BundlePlanPath
    }
    else {
        Join-Path $ProjectRoot $BundlePlanPath
    }
    if (-not (Test-Path -LiteralPath $resolvedPlanPath -PathType Leaf)) {
        throw "Bundle plan not found: $resolvedPlanPath"
    }
    if (-not $BundlePlanSha256 -or $BundlePlanSha256 -notmatch '^[0-9a-fA-F]{64}$') {
        throw 'BundlePlanSha256 must be a 64-character SHA-256 value.'
    }
    $actualPlanSha256 = (Get-FileHash -LiteralPath $resolvedPlanPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualPlanSha256 -ne $BundlePlanSha256.ToLowerInvariant()) {
        throw 'Bundle plan hash mismatch.'
    }

    $bundlePlan = Get-Content -LiteralPath $resolvedPlanPath -Raw | ConvertFrom-Json
    if ([int]$bundlePlan.schema_version -ne 1) {
        throw 'Unsupported bundle plan schema version.'
    }
    foreach ($field in @(
        'allowed_agent_application_ids',
        'asset_ids',
        'component_ids',
        'gate_ids',
        'launcher_ids',
        'plan_fact_ids',
        'project_distribution_ids',
        'python_feature_ids',
        'runtime_capability_ids',
        'runtime_component_ids',
        'shell_ids'
    )) {
        Assert-BundlePlanArray -Plan $bundlePlan -Name $field
    }
    foreach ($field in @(
        'agent_id',
        'agent_lock_sha256',
        'artifact_name',
        'assurance',
        'config_template_id',
        'flavor_id',
        'runtime_contract_sha256',
        'target_id'
    )) {
        if (-not ($bundlePlan.PSObject.Properties.Name -contains $field) -or -not [string]$bundlePlan.$field) {
            throw "Bundle plan is missing required field: $field"
        }
    }

    $projectDistributions = @(
        'embedagent-core',
        'embedagent-protocol',
        'embedagent-host',
        'embedagent-composition',
        'embedagent-workflow-cpp',
        'embedagent'
    )
    Assert-ExactBundlePlanIds `
        -Name 'project distribution' `
        -Actual @($bundlePlan.project_distribution_ids) `
        -Expected $projectDistributions

    $resolvedRuntimeContractPath = if ([System.IO.Path]::IsPathRooted($RuntimeContractPath)) {
        $RuntimeContractPath
    }
    else {
        Join-Path $ProjectRoot $RuntimeContractPath
    }
    if (-not (Test-Path -LiteralPath $resolvedRuntimeContractPath -PathType Leaf)) {
        throw "Runtime contract not found: $resolvedRuntimeContractPath"
    }
    $runtimeContract = Get-Content -LiteralPath $resolvedRuntimeContractPath -Raw | ConvertFrom-Json
    if ([int]$runtimeContract.schema_version -ne 2) {
        throw 'Unsupported offline runtime contract schema version.'
    }

    $resolvedAssetManifestPath = if ([System.IO.Path]::IsPathRooted($AssetManifestPath)) {
        $AssetManifestPath
    }
    else {
        Join-Path $ProjectRoot $AssetManifestPath
    }
    if (-not (Test-Path -LiteralPath $resolvedAssetManifestPath -PathType Leaf)) {
        throw "Asset manifest not found: $resolvedAssetManifestPath"
    }
    $assetManifest = Get-Content -LiteralPath $resolvedAssetManifestPath -Raw | ConvertFrom-Json

    $knownLaunchers = @($runtimeContract.launchers | ForEach-Object { [string]$_.id })
    $knownGates = @($runtimeContract.release_gates | ForEach-Object { [string]$_.id })
    $knownRuntimeComponents = @($runtimeContract.runtime_components | ForEach-Object { [string]$_.id })
    $knownFeatures = @()
    foreach ($component in @($runtimeContract.runtime_components)) {
        $knownFeatures += @($component.python_feature_ids | ForEach-Object { [string]$_ })
    }
    $knownAssets = @($assetManifest.assets | ForEach-Object { [string]$_.id })
    Assert-KnownBundlePlanIds -Name 'shell' -Values @($bundlePlan.shell_ids) -KnownValues @('cli', 'tui', 'gui')
    Assert-KnownBundlePlanIds -Name 'launcher' -Values @($bundlePlan.launcher_ids) -KnownValues $knownLaunchers
    Assert-KnownBundlePlanIds -Name 'asset' -Values @($bundlePlan.asset_ids) -KnownValues $knownAssets
    Assert-KnownBundlePlanIds -Name 'Python feature' -Values @($bundlePlan.python_feature_ids) -KnownValues $knownFeatures
    Assert-KnownBundlePlanIds -Name 'gate' -Values @($bundlePlan.gate_ids) -KnownValues $knownGates
    Assert-KnownBundlePlanIds -Name 'runtime component' -Values @($bundlePlan.runtime_component_ids) -KnownValues $knownRuntimeComponents

    if ([string]$bundlePlan.target_id -notin @($runtimeContract.targets.PSObject.Properties.Name)) {
        throw "Bundle plan contains unknown target id: $($bundlePlan.target_id)"
    }
    if ([string]$bundlePlan.assurance -notin @('dev', 'release')) {
        throw "Bundle plan contains unknown assurance: $($bundlePlan.assurance)"
    }
    $selectedRuntimeComponents = @($runtimeContract.runtime_components | Where-Object {
        @($bundlePlan.runtime_component_ids) -contains [string]$_.id
    })
    $expectedAssets = @()
    $expectedFeatures = @()
    $expectedCapabilities = @()
    $expectedLaunchers = @()
    foreach ($component in $selectedRuntimeComponents) {
        $expectedAssets += @($component.asset_ids)
        $expectedFeatures += @($component.python_feature_ids)
        $expectedCapabilities += @($component.provides)
        $expectedLaunchers += @($component.launcher_ids)
    }
    foreach ($gate in @($runtimeContract.release_gates | Where-Object {
        @($bundlePlan.gate_ids) -contains [string]$_.id
    })) {
        if ($gate.PSObject.Properties.Name -contains 'launcher_ids') {
            $expectedLaunchers += @($gate.launcher_ids)
        }
    }
    Assert-SameBundlePlanIdSet -Name 'asset' -Actual @($bundlePlan.asset_ids) -Expected $expectedAssets
    Assert-SameBundlePlanIdSet -Name 'Python feature' -Actual @($bundlePlan.python_feature_ids) -Expected $expectedFeatures
    Assert-SameBundlePlanIdSet -Name 'runtime capability' -Actual @($bundlePlan.runtime_capability_ids) -Expected $expectedCapabilities
    Assert-SameBundlePlanIdSet -Name 'launcher' -Actual @($bundlePlan.launcher_ids) -Expected $expectedLaunchers
    $expectedShells = @($bundlePlan.component_ids | Where-Object { ([string]$_).StartsWith('shell.') } | ForEach-Object {
        ([string]$_).Substring('shell.'.Length)
    })
    Assert-SameBundlePlanIdSet -Name 'shell' -Actual @($bundlePlan.shell_ids) -Expected $expectedShells
    if (-not (@($bundlePlan.shell_ids) -contains 'cli') -or -not (@($bundlePlan.launcher_ids) -contains 'cli')) {
        throw 'Every offline bundle plan must select the CLI shell and launcher.'
    }
    if (-not (@($bundlePlan.allowed_agent_application_ids) -contains [string]$bundlePlan.agent_id)) {
        throw 'Bundle plan must allow its compiled Agent application id.'
    }

    $planDirectory = Split-Path -Parent $resolvedPlanPath
    $agentManifestPath = Join-Path $planDirectory 'agent.json'
    $agentLockPath = Join-Path $planDirectory 'agent.lock.json'
    foreach ($path in @($agentManifestPath, $agentLockPath)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Compiled Agent manifest not found: $path"
        }
    }
    $actualAgentLockSha256 = (Get-FileHash -LiteralPath $agentLockPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualAgentLockSha256 -ne [string]$bundlePlan.agent_lock_sha256) {
        throw 'Bundle plan Agent lock hash mismatch.'
    }
    $agentManifest = Get-Content -LiteralPath $agentManifestPath -Raw | ConvertFrom-Json
    $agentLock = Get-Content -LiteralPath $agentLockPath -Raw | ConvertFrom-Json
    if (
        [int]$agentManifest.schema_version -ne 1 -or
        [int]$agentLock.schema_version -ne 1 -or
        [string]$agentManifest.agent_id -ne [string]$bundlePlan.agent_id -or
        [string]$agentLock.agent_id -ne [string]$bundlePlan.agent_id
    ) {
        throw 'Compiled Agent manifests do not match the bundle plan.'
    }
    Assert-SameBundlePlanIdSet `
        -Name 'Agent manifest component' `
        -Actual @($agentManifest.components | ForEach-Object { [string]$_.component_id }) `
        -Expected @($bundlePlan.component_ids)
    Assert-SameBundlePlanIdSet `
        -Name 'Agent lock component' `
        -Actual @($agentLock.components | ForEach-Object { [string]$_.component_id }) `
        -Expected @($bundlePlan.component_ids)

    return [ordered]@{
        plan = $bundlePlan
        plan_path = (Resolve-Path -LiteralPath $resolvedPlanPath).Path
        plan_sha256 = $actualPlanSha256
        agent_manifest_path = (Resolve-Path -LiteralPath $agentManifestPath).Path
        agent_lock_path = (Resolve-Path -LiteralPath $agentLockPath).Path
        runtime_contract = $runtimeContract
        runtime_contract_path = (Resolve-Path -LiteralPath $resolvedRuntimeContractPath).Path
        asset_manifest = $assetManifest
        asset_manifest_path = (Resolve-Path -LiteralPath $resolvedAssetManifestPath).Path
    }
}

function Assert-BundleManifestPlanBinding {
    param(
        [object]$Manifest,
        [System.Collections.IDictionary]$PlanState,
        [string]$BundleRoot
    )

    $plan = $PlanState.plan
    foreach ($binding in @(
        @('flavor_id', 'flavor_id'),
        @('bundle_plan_sha256', 'plan_sha256'),
        @('agent_lock_sha256', 'agent_lock_sha256')
    )) {
        $manifestField = [string]$binding[0]
        $planField = [string]$binding[1]
        $expected = if ($binding[1] -eq 'plan_sha256') {
            [string]$PlanState.plan_sha256
        }
        else {
            [string]$plan.$planField
        }
        if (-not ($Manifest.PSObject.Properties.Name -contains $manifestField) -or [string]$Manifest.$manifestField -ne $expected) {
            throw "Staging manifest does not match bundle plan field: $manifestField"
        }
    }
    foreach ($binding in @(
        @('allowed_agent_application_ids', 'allowed_agent_application_ids'),
        @('shell_ids', 'shell_ids'),
        @('runtime_component_ids', 'runtime_component_ids'),
        @('resolved_asset_ids', 'asset_ids'),
        @('python_feature_ids', 'python_feature_ids'),
        @('staged_launcher_ids', 'launcher_ids'),
        @('gate_ids', 'gate_ids')
    )) {
        $manifestField = [string]$binding[0]
        $planField = [string]$binding[1]
        if (-not ($Manifest.PSObject.Properties.Name -contains $manifestField)) {
            throw "Staging manifest is missing bundle plan field: $manifestField"
        }
        $actual = @($Manifest.$manifestField)
        $expected = @($plan.$planField)
        if ($actual.Count -ne $expected.Count) {
            throw "Staging manifest does not match bundle plan field: $manifestField"
        }
        for ($index = 0; $index -lt $expected.Count; $index++) {
            if ([string]$actual[$index] -ne [string]$expected[$index]) {
                throw "Staging manifest does not match bundle plan field: $manifestField"
            }
        }
    }

    $stagedPlanPath = Join-Path $BundleRoot 'manifests\bundle-plan.json'
    $stagedAgentPath = Join-Path $BundleRoot 'manifests\agent.json'
    $stagedAgentLockPath = Join-Path $BundleRoot 'manifests\agent.lock.json'
    foreach ($path in @($stagedPlanPath, $stagedAgentPath, $stagedAgentLockPath)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Staging bundle is missing compiled plan or Agent manifest: $path"
        }
    }
    $stagedPlanSha256 = (Get-FileHash -LiteralPath $stagedPlanPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $stagedAgentLockSha256 = (Get-FileHash -LiteralPath $stagedAgentLockPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($stagedPlanSha256 -ne [string]$PlanState.plan_sha256) {
        throw 'Staged bundle plan hash mismatch.'
    }
    if ($stagedAgentLockSha256 -ne [string]$plan.agent_lock_sha256) {
        throw 'Staged Agent lock hash mismatch.'
    }
}

function Resolve-PackageBundlePlan {
    param(
        [string]$ProjectRoot,
        [object]$Config,
        [string]$Flavor,
        [string]$Profile
    )

    $reportsRoot = Resolve-ConfigPath -ProjectRoot $ProjectRoot -Path ([string]$Config.paths.reports_root)
    $compilerPath = Resolve-ConfigPath -ProjectRoot $ProjectRoot -Path ([string]$Config.tooling.compile_bundle_plan)
    $runtimeContractPath = Join-Path $ProjectRoot 'scripts\offline-runtime-contract.json'
    $assetManifestPath = Resolve-ConfigPath -ProjectRoot $ProjectRoot -Path ([string]$Config.paths.asset_manifest)
    $planRoot = Join-Path $reportsRoot ('plan-{0}-{1}' -f $Flavor, $Profile)
    $planReportPath = Join-Path $reportsRoot ('plan-{0}-{1}-report.json' -f $Flavor, $Profile)
    $pythonPath = Resolve-PackagePythonPath -ProjectRoot $ProjectRoot
    $compilerOutput = @(& $pythonPath $compilerPath `
        --flavor $Flavor `
        --target 'win7-x64-portable' `
        --assurance $Profile `
        --runtime-contract $runtimeContractPath `
        --asset-manifest $assetManifestPath `
        --output-dir $planRoot `
        --json-report $planReportPath 2>&1)
    $compilerExitCode = $LASTEXITCODE
    $planReport = $null
    if (Test-Path -LiteralPath $planReportPath -PathType Leaf) {
        $planReport = Get-Content -LiteralPath $planReportPath -Raw | ConvertFrom-Json
    }
    if ($compilerExitCode -ne 0 -or -not $planReport -or -not $planReport.ok) {
        $errorCode = if ($planReport -and $planReport.error_code) { [string]$planReport.error_code } else { 'bundle_plan_compilation_failed' }
        $message = if ($planReport -and $planReport.message) { [string]$planReport.message } else { ($compilerOutput -join '; ') }
        throw ('Bundle plan compilation failed ({0}): {1}' -f $errorCode, $message)
    }
    $planPath = [string]$planReport.plan_path
    if (-not (Test-Path -LiteralPath $planPath -PathType Leaf)) {
        throw "Compiled bundle plan not found: $planPath"
    }
    $planHash = (Get-FileHash -LiteralPath $planPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($planHash -ne [string]$planReport.plan_sha256) {
        throw 'Compiled bundle plan hash does not match its compiler report.'
    }
    $plan = Get-Content -LiteralPath $planPath -Raw | ConvertFrom-Json
    if ([int]$plan.schema_version -ne 1 -or [string]$plan.flavor_id -ne $Flavor) {
        throw 'Compiled bundle plan identity does not match the package request.'
    }
    return [ordered]@{
        reports_root = $reportsRoot
        plan = $plan
        plan_path = $planPath
        plan_sha256 = $planHash
    }
}

function New-PackageStageTimer {
    $started = Get-Date
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    return [ordered]@{
        started_at = $started.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        stopwatch = $stopwatch
    }
}

function Add-StageResult {
    param(
        [object]$Report,
        [string]$Name,
        [string]$Status,
        [int]$ExitCode,
        [hashtable]$Summary,
        [object]$StageTimer = $null
    )

    $target = $Report
    if ($target.PSObject.Properties.Name -contains 'Value') {
        $target = $target.Value
    }
    if ($target -isnot [System.Collections.IDictionary] -and ($target.PSObject.Properties.Name -contains 'Value')) {
        $target = $target.Value
    }

    $finished = Get-Date
    $startedAt = $finished.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    $durationMs = 0
    if ($StageTimer -and $StageTimer -is [System.Collections.IDictionary]) {
        if ($StageTimer.Contains('started_at')) {
            $startedAt = [string]$StageTimer['started_at']
        }
        if ($StageTimer.Contains('stopwatch') -and $StageTimer['stopwatch']) {
            $timer = $StageTimer['stopwatch']
            $timer.Stop()
            $durationMs = [int64]$timer.ElapsedMilliseconds
        }
    }

    $stage = [ordered]@{
        name = $Name
        status = $Status
        exit_code = $ExitCode
        started_at = $startedAt
        finished_at = $finished.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        duration_ms = $durationMs
        summary = $Summary
    }
    $target['stages'] += $stage
    if ($Status -eq 'fail') {
        $target['blocking_issues'] += ('Stage failed: ' + $Name)
    }
    elseif ($Status -eq 'warn') {
        $target['warnings'] += ('Stage warned: ' + $Name)
    }
}

function Complete-PackageReport {
    param(
        [object]$Report
    )

    $report = $Report
    if ($report.PSObject.Properties.Name -contains 'Value') {
        $report = $report.Value
    }
    if ($report -isnot [System.Collections.IDictionary] -and ($report.PSObject.Properties.Name -contains 'Value')) {
        $report = $report.Value
    }
    $hasFailures = @($report['blocking_issues']).Count -gt 0
    if ($report['command'] -eq 'doctor') {
        $report['command_status'] = if ($hasFailures) { 'NOT_READY' } else { 'READY' }
        $report['final_status'] = $null
        return
    }

    if ($hasFailures) {
        $report['final_status'] = 'NOT_READY'
        $report['artifact_status'] = 'provisional'
        $report['publishable'] = $false
    }
    elseif ($report['command'] -eq 'release' -or $report['profile'] -eq 'release') {
        $report['final_status'] = 'READY'
        $report['artifact_status'] = 'verified'
        $report['publishable'] = $true
    }
    else {
        $report['final_status'] = 'DEV_ONLY'
        $report['artifact_status'] = 'provisional'
        $report['publishable'] = $false
    }
    $report['command_status'] = 'completed'
}

function Get-PackageExitCode {
    param(
        [System.Collections.IDictionary]$Report
    )

    if ($Report['command'] -eq 'doctor') {
        return $(if ($Report['command_status'] -eq 'READY') { 0 } else { 1 })
    }

    switch ($Report['final_status']) {
        'READY' { return 0 }
        'TARGET_READY' { return 0 }
        'DEV_ONLY' { return 0 }
        'NOT_READY' { return 1 }
        default { return 2 }
    }
}

function New-PackageContext {
    param(
        [string]$ProjectRoot,
        [object]$Config,
        [string]$ConfigPath,
        [string]$Command,
        [string]$RequestedProfile,
        [string]$RequestedFlavor,
        [string]$BundleRoot,
        [string]$OutputRoot,
        [string]$ArtifactName,
        [bool]$AllowDownload,
        [bool]$NoZip,
        [bool]$Strict,
        [bool]$Reproducible = $false,
        [string]$ReproducibilityRoot = ''
    )

    $effectiveProfile = if ($RequestedProfile) {
        $RequestedProfile
    }
    elseif ($Command -eq 'release') {
        'release'
    }
    else {
        [string]$Config.default_profile
    }

    $profileConfig = $Config.profiles.$effectiveProfile
    if (-not $profileConfig) {
        throw "Unknown packaging profile: $effectiveProfile"
    }

    $effectiveFlavor = if ($RequestedFlavor) {
        $RequestedFlavor
    }
    else {
        [string]$Config.default_flavor
    }
    if (-not $effectiveFlavor) {
        throw 'Package config must define default_flavor when no flavor is requested.'
    }
    $planState = Resolve-PackageBundlePlan `
        -ProjectRoot $ProjectRoot `
        -Config $Config `
        -Flavor $effectiveFlavor `
        -Profile $effectiveProfile

    $configOrigin = [string]$Config.metadata.config_origin
    $executionKind = if ($configOrigin -eq 'production') { 'release' } else { 'test' }
    $sourceRevision = (& git -C $ProjectRoot rev-parse HEAD 2>$null | Out-String).Trim()
    if (-not $sourceRevision) {
        if ($configOrigin -eq 'production') {
            throw 'Unable to resolve source revision for production package config.'
        }
        $sourceRevision = 'unknown'
    }
    $reportsRoot = [string]$planState.reports_root
    $effectiveArtifactName = if ($ArtifactName) { $ArtifactName } else { [string]$planState.plan.artifact_name }
    $configuredBuildRoot = Resolve-ConfigPath -ProjectRoot $ProjectRoot -Path ([string]$Config.paths.build_root)
    $artifactRoot = if ($BundleRoot) {
        Resolve-ConfigPath -ProjectRoot $ProjectRoot -Path $BundleRoot
    }
    else {
        Join-Path (Join-Path $configuredBuildRoot 'offline-dist') $effectiveArtifactName
    }
    return [ordered]@{
        run_id = [guid]::NewGuid().ToString('N')
        execution_kind = $executionKind
        config_origin = $configOrigin
        source_revision = $sourceRevision
        reports_root = $reportsRoot
        artifact_root = $artifactRoot
        project_root = $ProjectRoot
        config_path = $ConfigPath
        config = $Config
        command = $Command
        profile = $effectiveProfile
        flavor = $effectiveFlavor
        bundle_plan = $planState.plan
        bundle_plan_path = [string]$planState.plan_path
        bundle_plan_sha256 = [string]$planState.plan_sha256
        profile_config = $profileConfig
        bundle_root = $BundleRoot
        output_root = $OutputRoot
        artifact_name = $effectiveArtifactName
        allow_download = $AllowDownload -or [bool]$profileConfig.allow_download
        no_zip = $NoZip
        strict = $Strict
        reproducible = $Reproducible
        reproducibility_root = $ReproducibilityRoot
    }
}

function Get-GuiStaticAssetStatus {
    param(
        [string]$StaticRoot
    )

    $assetsRoot = Join-Path $StaticRoot 'assets'
    $required = [ordered]@{
        'index.html' = (Join-Path $StaticRoot 'index.html')
        'app.js' = (Join-Path $assetsRoot 'app.js')
        'app.css' = (Join-Path $assetsRoot 'app.css')
        'katex.min.css' = (Join-Path $assetsRoot 'katex\katex.min.css')
    }
    $missing = @()
    foreach ($name in $required.Keys) {
        if (-not (Test-Path -LiteralPath $required[$name])) {
            $missing += $name
        }
    }
    return [ordered]@{
        ok = ($missing.Count -eq 0)
        static_root = $StaticRoot
        assets_root = $assetsRoot
        paths = $required
        missing = $missing
    }
}

function Get-GuiFrontendAssetStatus {
    param(
        [string]$ProjectRoot
    )

    $staticRoot = Join-Path $ProjectRoot 'src\embedagent\frontend\gui\static'
    $status = Get-GuiStaticAssetStatus -StaticRoot $staticRoot
    $status['project_root'] = $ProjectRoot
    $status['webapp_root'] = Join-Path $ProjectRoot 'src\embedagent\frontend\gui\webapp'
    return $status
}

function Get-GuiBundleAssetStatus {
    param(
        [string]$BundleRoot
    )

    $staticRoot = Join-Path $BundleRoot 'app\embedagent\frontend\gui\static'
    $status = Get-GuiStaticAssetStatus -StaticRoot $staticRoot
    $status['bundle_root'] = $BundleRoot
    return $status
}

function Ensure-GuiFrontendAssets {
    param(
        [string]$ProjectRoot,
        [switch]$ForceBuild
    )

    $before = Get-GuiFrontendAssetStatus -ProjectRoot $ProjectRoot
    if ($before.ok -and (-not $ForceBuild)) {
        return [ordered]@{
            ok = $true
            mode = 'prebuilt'
            static_root = $before.static_root
            assets_root = $before.assets_root
            missing = @()
        }
    }

    $webappDir = [string]$before.webapp_root
    if (-not (Test-Path -LiteralPath $webappDir)) {
        return [ordered]@{
            ok = $false
            mode = 'missing'
            reason = 'webapp_dir_missing'
            static_root = $before.static_root
            missing = @($before.missing)
            path = $webappDir
        }
    }

    $npmCmd = 'npm'
    try {
        $npmVersion = (& $npmCmd --version 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $npmVersion) {
            throw 'npm --version failed'
        }
    }
    catch {
        return [ordered]@{
            ok = $false
            mode = 'missing'
            reason = 'npm_not_found'
            static_root = $before.static_root
            missing = @($before.missing)
            hint = 'Install Node.js >= 18 on the build machine or restore prebuilt GUI static assets.'
        }
    }

    Push-Location $webappDir
    try {
        $oldEap = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            $installOutput = & $npmCmd install --force 2>&1
            $installExit = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $oldEap
        }
        if ($installExit -ne 0) {
            return [ordered]@{
                ok = $false
                mode = 'build_failed'
                reason = 'npm_install_failed'
                static_root = $before.static_root
                missing = @($before.missing)
                npm_version = $npmVersion
                error = ('npm install --force failed (exit {0}): {1}' -f $installExit, ($installOutput | Out-String).Trim())
            }
        }
        $oldEap = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            $buildOutput = & $npmCmd run build 2>&1
            $buildExit = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $oldEap
        }
        if ($buildExit -ne 0) {
            return [ordered]@{
                ok = $false
                mode = 'build_failed'
                reason = 'npm_build_failed'
                static_root = $before.static_root
                missing = @($before.missing)
                npm_version = $npmVersion
                error = ('npm run build failed (exit {0}): {1}' -f $LASTEXITCODE, ($buildOutput | Out-String).Trim())
            }
        }
    }
    finally {
        Pop-Location
    }

    $after = Get-GuiFrontendAssetStatus -ProjectRoot $ProjectRoot
    if (-not $after.ok) {
        return [ordered]@{
            ok = $false
            mode = 'build_failed'
            reason = 'assets_missing_after_build'
            static_root = $after.static_root
            missing = @($after.missing)
            npm_version = $npmVersion
        }
    }

    return [ordered]@{
        ok = $true
        mode = 'rebuilt'
        static_root = $after.static_root
        assets_root = $after.assets_root
        missing = @()
        npm_version = $npmVersion
    }
}

function New-PackageDoctorCheck {
    param(
        [string]$Name,
        [string]$Code,
        [bool]$Ok,
        [bool]$Blocking,
        [string]$Path,
        [string]$Detail = ''
    )

    return [ordered]@{
        name = $Name
        code = $Code
        ok = $Ok
        blocking = $Blocking
        path = $Path
        detail = $Detail
    }
}

function Get-PackageDoctorChecks {
    param(
        [System.Collections.IDictionary]$Context
    )

    $releaseBlocking = [string]::Equals([string]$Context.profile, 'release', [System.StringComparison]::OrdinalIgnoreCase)
    $checks = @()
    $projectRoot = [string]$Context.project_root
    $config = $Context.config
    $configPath = [string]$Context.config_path
    $checks += New-PackageDoctorCheck -Name 'config' -Code 'config' -Ok (Test-Path -LiteralPath $configPath) -Blocking $releaseBlocking -Path $configPath
    $assetManifestPath = Resolve-ConfigPath -ProjectRoot $projectRoot -Path ([string]$config.paths.asset_manifest)
    $checks += New-PackageDoctorCheck -Name 'asset_manifest' -Code 'asset_manifest' -Ok (Test-Path -LiteralPath $assetManifestPath) -Blocking $releaseBlocking -Path $assetManifestPath

    $toolingPaths = @(
        (Resolve-ConfigPath -ProjectRoot $projectRoot -Path ([string]$config.tooling.compile_bundle_plan)),
        (Resolve-ConfigPath -ProjectRoot $projectRoot -Path ([string]$config.tooling.export_dependencies)),
        (Resolve-ConfigPath -ProjectRoot $projectRoot -Path ([string]$config.tooling.build_gui_launcher)),
        (Resolve-ConfigPath -ProjectRoot $projectRoot -Path ([string]$config.tooling.prepare_bundle)),
        (Resolve-ConfigPath -ProjectRoot $projectRoot -Path ([string]$config.tooling.build_bundle)),
        (Resolve-ConfigPath -ProjectRoot $projectRoot -Path ([string]$config.tooling.validate_bundle)),
        (Resolve-ConfigPath -ProjectRoot $projectRoot -Path ([string]$config.tooling.check_dependencies))
    )
    foreach ($toolPath in $toolingPaths) {
        $toolName = [System.IO.Path]::GetFileName($toolPath)
        $checks += New-PackageDoctorCheck -Name ('tool:' + $toolName) -Code ('tool.' + $toolName) -Ok (Test-Path -LiteralPath $toolPath) -Blocking $releaseBlocking -Path $toolPath
    }

    $npmOk = $false
    $npmVersion = ''
    try {
        $npmVersion = (& npm --version 2>&1 | Out-String).Trim()
        $npmOk = ($LASTEXITCODE -eq 0) -and ($npmVersion -ne '')
    }
    catch {
        $npmOk = $false
    }
    $prebuiltFrontendStatus = Get-GuiFrontendAssetStatus -ProjectRoot $projectRoot
    $prebuiltFrontendOk = [bool]$prebuiltFrontendStatus.ok
    $npmPath = if ($npmOk) { 'npm (' + $npmVersion + ')' } else { [string]$prebuiltFrontendStatus.static_root }
    $checks += New-PackageDoctorCheck -Name 'runtime:npm' -Code 'runtime.npm' -Ok ($npmOk -or $prebuiltFrontendOk) -Blocking $releaseBlocking -Path $npmPath

    $pythonPath = ''
    $pythonVersion = ''
    $pythonCandidates = @(Get-PackagePythonCandidates -ProjectRoot $projectRoot)
    if ($pythonCandidates.Count -gt 0) {
        $pythonPath = [string]$pythonCandidates[0]
        try {
            $pythonVersion = (& $pythonPath --version 2>&1 | Out-String).Trim()
        }
        catch {
            $pythonVersion = ''
        }
    }
    $pythonOk = $pythonVersion -match '^Python 3\.8\.'
    $checks += New-PackageDoctorCheck -Name 'python:version' -Code 'python.version' -Ok $pythonOk -Blocking $releaseBlocking -Path $pythonPath -Detail $pythonVersion

    $assetManifest = $null
    try {
        if (Test-Path -LiteralPath $assetManifestPath) {
            $assetManifest = Get-Content -Raw -LiteralPath $assetManifestPath | ConvertFrom-Json
        }
    }
    catch {
        $assetManifest = $null
    }
    $cacheRoot = Resolve-ConfigPath -ProjectRoot $projectRoot -Path (Join-Path ([string]$config.paths.build_root) 'offline-cache')
    $requiredAssetIds = @($Context.bundle_plan.asset_ids)
    foreach ($assetId in $requiredAssetIds) {
        $asset = @($assetManifest.assets | Where-Object { [string]$_.id -eq [string]$assetId }) | Select-Object -First 1
        $cachePath = if ($asset) { Join-Path $cacheRoot ([string]$asset.cache_relpath) } else { Join-Path $cacheRoot ([string]$assetId) }
        $cacheOk = [bool]$asset -and (Test-Path -LiteralPath $cachePath -PathType Leaf)
        if ($Context.allow_download -and -not $cacheOk) {
            $cacheOk = $true
        }
        $checks += New-PackageDoctorCheck -Name ('asset:' + $assetId) -Code ('asset.cache.' + $assetId) -Ok $cacheOk -Blocking $releaseBlocking -Path $cachePath
    }

    $webviewAsset = @($assetManifest.assets | Where-Object { [string]$_.id -eq 'webview2_fixed_runtime_x64' }) | Select-Object -First 1
    $webviewPath = if ($webviewAsset) { Join-Path $cacheRoot ([string]$webviewAsset.cache_relpath) } else { Join-Path $cacheRoot 'webview2' }
    $webviewOk = [bool]$webviewAsset -and (Test-Path -LiteralPath $webviewPath -PathType Leaf)
    if ($Context.allow_download -and -not $webviewOk) {
        $webviewOk = $true
    }
    $checks += New-PackageDoctorCheck -Name 'asset:webview2_fixed_runtime_x64' -Code 'asset.cache.webview2_fixed_runtime_x64' -Ok $webviewOk -Blocking $releaseBlocking -Path $webviewPath

    $llvmRoot = Resolve-ConfigPath -ProjectRoot $projectRoot -Path ([string]$config.paths.llvm_root)
    $llvmMain = Join-Path $llvmRoot 'bin\clang.exe'
    $checks += New-PackageDoctorCheck -Name 'toolchain:llvm' -Code 'toolchain.llvm' -Ok (Test-Path -LiteralPath $llvmMain -PathType Leaf) -Blocking $releaseBlocking -Path $llvmMain
    foreach ($childName in @('clang.exe', 'clang++.exe', 'clang-cl.exe', 'clang-tidy.exe', 'clang-analyzer.bat', 'llvm-profdata.exe', 'llvm-cov.exe')) {
        $childPath = Join-Path $llvmRoot ('bin\' + $childName)
        $checks += New-PackageDoctorCheck -Name ('toolchain:llvm:' + $childName) -Code ('toolchain.llvm.' + $childName) -Ok (Test-Path -LiteralPath $childPath -PathType Leaf) -Blocking $releaseBlocking -Path $childPath
    }

    $distributionNames = @($Context.bundle_plan.project_distribution_ids)
    foreach ($distributionName in $distributionNames) {
        $projectPath = if ($distributionName -eq 'embedagent') {
            Join-Path $projectRoot 'pyproject.toml'
        }
        elseif ($distributionName -eq 'embedagent-workflow-cpp') {
            Join-Path $projectRoot 'packages\embedagent-workflow-cpp\pyproject.toml'
        }
        else {
            Join-Path $projectRoot ('packages\' + $distributionName + '\pyproject.toml')
        }
        $checks += New-PackageDoctorCheck -Name ('project:' + $distributionName) -Code ('project.' + $distributionName) -Ok (Test-Path -LiteralPath $projectPath -PathType Leaf) -Blocking $releaseBlocking -Path $projectPath
    }

    $wheelhouseRoot = Resolve-ConfigPath -ProjectRoot $projectRoot -Path (Join-Path ([string]$config.paths.site_packages_export_root) 'wheels')
    $wheelhouseOk = $true
    $wheelhouseDetail = 'will be created by deps'
    if (Test-Path -LiteralPath $wheelhouseRoot) {
        $wheelhouseItem = Get-Item -LiteralPath $wheelhouseRoot -Force
        $wheelhouseOk = (($wheelhouseItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -eq 0)
        if ($wheelhouseOk) {
            foreach ($entry in @(Get-ChildItem -LiteralPath $wheelhouseRoot -Force)) {
                if ($entry.PSIsContainer -or $entry.Extension -ne '.whl') {
                    $wheelhouseOk = $false
                    $wheelhouseDetail = 'unsafe entry: ' + $entry.Name
                    break
                }
            }
        }
    }
    $checks += New-PackageDoctorCheck -Name 'wheelhouse:output_root' -Code 'wheelhouse.output_root' -Ok $wheelhouseOk -Blocking $releaseBlocking -Path $wheelhouseRoot -Detail $wheelhouseDetail

    $buildRoot = Resolve-ConfigPath -ProjectRoot $projectRoot -Path ([string]$config.paths.build_root)
    $buildParent = Split-Path -Qualifier $buildRoot
    $freeBytes = 0
    $freeKnown = $false
    try {
        $driveName = $buildParent.TrimEnd('\').TrimEnd(':')
        $drive = Get-PSDrive -Name $driveName -ErrorAction Stop
        $freeBytes = [int64]$drive.Free
        $freeKnown = $true
    }
    catch {
        $freeKnown = $false
    }
    $minimumBytes = 0
    if ($Context.profile_config.PSObject.Properties.Name -contains 'minimum_free_bytes') {
        if ($Context.profile_config.minimum_free_bytes) {
            $minimumBytes = [int64]$Context.profile_config.minimum_free_bytes
        }
    }
    $freeOk = (-not $freeKnown) -or ($freeBytes -ge $minimumBytes)
    $checks += New-PackageDoctorCheck -Name 'disk:output_free_space' -Code 'disk.output_free_space' -Ok $freeOk -Blocking $releaseBlocking -Path $buildRoot -Detail ([string]$freeBytes)

    return @($checks)
}

function Invoke-PackageDoctor {
    param(
        [System.Collections.IDictionary]$Context
    )

    Write-PackageLog "[doctor] Running environment checks..."
    $report = New-PackageContextReport -Context $Context
    $doctorChecks = @(Get-PackageDoctorChecks -Context $Context)
    foreach ($check in $doctorChecks) {
        $status = if ($check.ok) { 'OK' } elseif ($check.blocking) { 'FAIL' } else { 'WARN' }
        Write-PackageLog ("[doctor]   {0}: {1} ({2})" -f $check.name, $status, $check.path)
        if (-not $check.ok) {
            if ($check.blocking) {
                $report.blocking_issues += ([string]$check.code + ': ' + [string]$check.path)
            }
            else {
                $report.warnings += ([string]$check.code + ': ' + [string]$check.path)
            }
        }
    }
    $report.doctor_checks = $doctorChecks
    Complete-PackageReport -Report ([ref]$report)

    $overall = if ($report.command_status -eq 'READY') { 'READY' } else { 'NOT_READY' }
    Write-PackageLog ("[doctor] Overall status: {0}" -f $overall)
    return $report
}

function Resolve-ToolPath {
    param(
        [System.Collections.IDictionary]$Context,
        [string]$RelativePath
    )

    return Resolve-ConfigPath -ProjectRoot $Context.project_root -Path $RelativePath
}

function Get-PackageRequiredAssetIds {
    param(
        [System.Collections.IDictionary]$Context
    )

    $requiredAssets = @()
    foreach ($assetId in @($Context.bundle_plan.asset_ids)) {
        $value = "$assetId".Trim()
        if ($value) {
            $requiredAssets += $value
        }
    }
    return @($requiredAssets | Select-Object -Unique)
}

function Get-PackagePythonCandidates {
    param(
        [string]$ProjectRoot
    )

    $candidates = @()
    if ($env:EMBEDAGENT_PYTHON) {
        $candidates += [string]$env:EMBEDAGENT_PYTHON
    }
    if ($ProjectRoot) {
        $candidates += (Join-Path $ProjectRoot '.venv\Scripts\python.exe')
    }

    $resolved = @()
    foreach ($candidate in $candidates | Select-Object -Unique) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            $resolved += (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    Write-Output -NoEnumerate @($resolved)
    return
}

function Resolve-PackagePythonPath {
    param(
        [string]$ProjectRoot
    )

    $candidates = Get-PackagePythonCandidates -ProjectRoot $ProjectRoot
    if (@($candidates).Count -eq 0) {
        $expectedPath = if ($ProjectRoot) {
            Join-Path $ProjectRoot '.venv\Scripts\python.exe'
        }
        else {
            '.venv\Scripts\python.exe'
        }
        throw ('Expected project virtualenv Python at {0} or an explicit EMBEDAGENT_PYTHON override. Run ''uv sync --python 3.8.10'' to provision the locked environment.' -f $expectedPath)
    }
    return $candidates[0]
}

function Resolve-PackagePowerShellPath {
    $currentProcess = Get-Process -Id $PID -ErrorAction SilentlyContinue
    if ($currentProcess -and $currentProcess.Path -and (Test-Path -LiteralPath $currentProcess.Path)) {
        return $currentProcess.Path
    }

    foreach ($commandName in @('pwsh', 'powershell')) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue
        if ($command -and $command.Source -and (Test-Path -LiteralPath $command.Source)) {
            return $command.Source
        }
    }

    throw 'PowerShell executable not found for packaging.'
}

function Invoke-StageScript {
    param(
        [string]$ProjectRoot,
        [string]$ScriptPath,
        [string[]]$Arguments
    )

    $extension = [System.IO.Path]::GetExtension($ScriptPath).ToLowerInvariant()
    if ($extension -eq '.py') {
        $pythonCandidates = Get-PackagePythonCandidates -ProjectRoot $ProjectRoot
        if (@($pythonCandidates).Count -eq 0) {
            $null = Resolve-PackagePythonPath -ProjectRoot $ProjectRoot
        }

        $errors = @()
        foreach ($pythonPath in $pythonCandidates) {
            try {
                $result = & $pythonPath $ScriptPath @Arguments 2>&1
                if ($LASTEXITCODE -eq 0) {
                    return $result
                }
                $errors += ('{0} exited with code {1}' -f $pythonPath, $LASTEXITCODE)
            }
            catch {
                $errors += ('{0} failed: {1}' -f $pythonPath, $_.Exception.Message)
            }
        }
        throw ('Python stage script failed for all candidates. ' + ($errors -join '; '))
    }
    if ($extension -eq '.ps1') {
        $powerShellPath = Resolve-PackagePowerShellPath
        Write-PackageLog ("[stage] Invoking {0}..." -f $ScriptPath)
        $procArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $ScriptPath) + $Arguments
        if ($Global:PackageJsonMode) {
            # In JSON mode, capture output so it does not pollute stdout.
            $null = & $powerShellPath @procArgs 2>&1
            if ($LASTEXITCODE -ne 0) {
                throw ('PowerShell stage script failed: {0} (exit {1})' -f $ScriptPath, $LASTEXITCODE)
            }
        } else {
            & $powerShellPath @procArgs
            $exitCode = $LASTEXITCODE
            Write-PackageLog ("[stage]   exited {0}: {1}" -f $exitCode, $ScriptPath)
            if ($exitCode -ne 0) {
                throw ('PowerShell stage script failed: {0} (exit {1})' -f $ScriptPath, $exitCode)
            }
        }
        return
    }
    throw "Unsupported stage script extension: $ScriptPath"
}

function New-ReportPath {
    param(
        [System.Collections.IDictionary]$Context,
        [string]$StageName
    )

    $reportsRoot = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.reports_root)
    if (-not (Test-Path -LiteralPath $reportsRoot)) {
        New-Item -ItemType Directory -Path $reportsRoot -Force | Out-Null
    }
    return Join-Path $reportsRoot ($StageName + '.json')
}

function Invoke-PackageDeps {
    param(
        [System.Collections.IDictionary]$Context,
        [ref]$Report
    )

    $scriptPath = Resolve-ToolPath -Context $Context -RelativePath ([string]$Context.config.tooling.export_dependencies)
    $jsonPath = New-ReportPath -Context $Context -StageName 'deps'
    $outputRoot = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.site_packages_export_root)
    $uvCacheRoot = if ($Context.config.paths.PSObject.Properties.Name -contains 'uv_cache_root') {
        Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.uv_cache_root)
    }
    else {
        Join-Path $Context.project_root 'build\offline-cache\uv'
    }
    $arguments = @(
        '--output-dir', $outputRoot,
        '--json-report', $jsonPath,
        '--cache-dir', $uvCacheRoot,
        '--bundle-plan', [string]$Context.bundle_plan_path,
        '--bundle-plan-sha256', [string]$Context.bundle_plan_sha256
    )
    $offlineDependencyBuild = $false
    if ($Context.profile_config.PSObject.Properties.Name -contains 'offline_dependency_build') {
        $offlineDependencyBuild = [bool]$Context.profile_config.offline_dependency_build
    }
    elseif ($Context.profile -eq 'release') {
        $offlineDependencyBuild = $true
    }
    if ($offlineDependencyBuild) {
        $arguments += '--offline'
    }
    $timer = New-PackageStageTimer
    $null = Invoke-StageScript -ProjectRoot $Context.project_root -ScriptPath $scriptPath -Arguments $arguments
    $payload = Get-Content -LiteralPath $jsonPath -Raw | ConvertFrom-Json
    $expectedDistributions = @($Context.bundle_plan.project_distribution_ids)
    $actualDistributions = @()
    if ($payload.PSObject.Properties.Name -contains 'project_distributions') {
        $actualDistributions = @($payload.project_distributions)
    }
    $actualWheels = @()
    if ($payload.PSObject.Properties.Name -contains 'project_wheels') {
        $actualWheels = @($payload.project_wheels)
    }
    $wheelHashCount = 0
    if (($payload.PSObject.Properties.Name -contains 'wheel_hashes') -and $payload.wheel_hashes) {
        $wheelHashCount = @($payload.wheel_hashes.PSObject.Properties).Count
    }
    $hasSixWheelContract = ($expectedDistributions.Count -eq 6) -and ($payload.PSObject.Properties.Name -contains 'project_distributions')
    $depsOk = if ($hasSixWheelContract) {
        [bool]$payload.ok -and $actualDistributions.Count -eq $expectedDistributions.Count -and (($actualDistributions -join '|' ) -eq ($expectedDistributions -join '|' )) -and $actualWheels.Count -eq 6 -and $wheelHashCount -eq 6
    } else {
        [bool]$payload.ok
    }
    $actualWheelHashes = $null
    if ($payload.PSObject.Properties.Name -contains 'wheel_hashes') {
        $actualWheelHashes = $payload.wheel_hashes
    }
    $summary = @{
        report = $jsonPath
        project_distributions = $actualDistributions
        project_wheels = $actualWheels
        wheel_hashes = $actualWheelHashes
        output_root = $outputRoot
    }
    if (-not $depsOk) {
        $Report.Value.blocking_issues += 'deps: exact six-wheel report handoff failed'
    }
    $depsStatus = if ($depsOk) { 'pass' } else { 'fail' }
    $depsExitCode = if ($depsOk) { 0 } else { 1 }
    Add-StageResult -Report $Report -Name 'deps' -Status $depsStatus -ExitCode $depsExitCode -Summary $summary -StageTimer $timer
}

function Invoke-FrontendBuild {
    param(
        [System.Collections.IDictionary]$Context,
        [ref]$Report
    )

    Write-PackageLog "[assemble] Building GUI frontend assets..."
    $timer = New-PackageStageTimer
    $result = Ensure-GuiFrontendAssets -ProjectRoot $Context.project_root -ForceBuild
    if (-not $result.ok) {
        Write-PackageLog ("[assemble]   frontend_build FAILED: {0}" -f $result.reason)
        Add-StageResult -Report $Report -Name 'frontend_build' -Status 'fail' -ExitCode 1 -Summary $result -StageTimer $timer
        return
    }
    Write-PackageLog ("[assemble]   frontend_build OK ({0})" -f $result.mode)
    Add-StageResult -Report $Report -Name 'frontend_build' -Status 'pass' -ExitCode 0 -Summary $result -StageTimer $timer
}

function Get-GuiLauncherOutputPath {
    param(
        [System.Collections.IDictionary]$Context
    )

    $outputRoot = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.gui_launcher_build_root)
    return Join-Path $outputRoot 'embedagent-gui.exe'
}

function Invoke-GuiLauncherBuild {
    param(
        [System.Collections.IDictionary]$Context,
        [ref]$Report
    )

    $scriptPath = Resolve-ToolPath -Context $Context -RelativePath ([string]$Context.config.tooling.build_gui_launcher)
    $outputPath = Get-GuiLauncherOutputPath -Context $Context
    $summary = @{
        script = $scriptPath
        output = $outputPath
    }

    Write-PackageLog "[assemble] Building native GUI launcher..."
    $timer = New-PackageStageTimer
    try {
        $null = Invoke-StageScript -ProjectRoot $Context.project_root -ScriptPath $scriptPath -Arguments @('-OutputPath', $outputPath)
    }
    catch {
        $summary.error = $_.Exception.Message
        Write-PackageLog ("[assemble]   gui_launcher_build FAILED: {0}" -f $_.Exception.Message)
        Add-StageResult -Report $Report -Name 'gui_launcher_build' -Status 'fail' -ExitCode 1 -Summary $summary -StageTimer $timer
        return ''
    }

    if (-not (Test-Path -LiteralPath $outputPath)) {
        $summary.error = 'launcher_output_missing'
        Write-PackageLog ("[assemble]   gui_launcher_build FAILED: output missing at {0}" -f $outputPath)
        Add-StageResult -Report $Report -Name 'gui_launcher_build' -Status 'fail' -ExitCode 1 -Summary $summary -StageTimer $timer
        return ''
    }

    Write-PackageLog ("[assemble]   gui_launcher_build OK ({0})" -f $outputPath)
    Add-StageResult -Report $Report -Name 'gui_launcher_build' -Status 'pass' -ExitCode 0 -Summary $summary -StageTimer $timer
    return $outputPath
}

function Invoke-ReleaseIdentity {
    param(
        [System.Collections.IDictionary]$Context
    )

    if ($Context.profile -ne 'release') {
        return $null
    }
    if (-not ($Context.config.paths.PSObject.Properties.Name -contains 'release_identity')) {
        return $null
    }
    $identityScript = Join-Path $Context.project_root 'scripts\create-release-identity.py'
    $identityPath = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.release_identity)
    $wheelRoot = Join-Path (Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.site_packages_export_root)) 'wheels'
    $guiStaticRoot = Join-Path $Context.project_root 'src\embedagent\frontend\gui\static'
    $assetManifestPath = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.asset_manifest)
    $runtimeContractPath = Join-Path $Context.project_root 'scripts\offline-runtime-contract.json'
    if (-not (Test-Path -LiteralPath $identityScript -PathType Leaf)) {
        throw "Release identity script not found: $identityScript"
    }
    if (-not (Test-Path -LiteralPath $wheelRoot -PathType Container)) {
        throw "Release identity wheelhouse not found: $wheelRoot"
    }
    $arguments = @(
        '--project-root', $Context.project_root,
        '--profile', $Context.profile,
        '--wheel-dir', $wheelRoot,
        '--bundle-plan', [string]$Context.bundle_plan_path,
        '--asset-manifest', $assetManifestPath,
        '--runtime-contract', $runtimeContractPath,
        '--output', $identityPath
    )
    if (@($Context.bundle_plan.shell_ids) -contains 'gui') {
        $arguments += @('--gui-static-root', $guiStaticRoot)
    }
    $null = Invoke-StageScript -ProjectRoot $Context.project_root -ScriptPath $identityScript -Arguments $arguments
    $identity = Get-Content -LiteralPath $identityPath -Raw | ConvertFrom-Json
    if (@($identity.project_distributions).Count -ne 6 -or @($identity.wheels).Count -ne 6) {
        throw 'Release identity must contain exactly six project distributions and wheels.'
    }
    if (
        [int]$identity.schema_version -ne 2 -or
        [string]$identity.flavor_id -ne [string]$Context.bundle_plan.flavor_id -or
        [string]$identity.target_id -ne [string]$Context.bundle_plan.target_id -or
        [string]$identity.bundle_plan_sha256 -ne [string]$Context.bundle_plan_sha256 -or
        [string]$identity.agent_lock_sha256 -ne [string]$Context.bundle_plan.agent_lock_sha256 -or
        (@($identity.gate_ids) -join '|') -ne (@($Context.bundle_plan.gate_ids) -join '|')
    ) {
        throw 'Release identity does not match the compiled bundle plan.'
    }
    $identityPlanPath = Join-Path (Split-Path -Parent $identityPath) 'bundle-plan.json'
    if (([System.IO.Path]::GetFullPath($identityPlanPath)) -ne ([System.IO.Path]::GetFullPath([string]$Context.bundle_plan_path))) {
        Copy-Item -LiteralPath ([string]$Context.bundle_plan_path) -Destination $identityPlanPath -Force
    }
    return [ordered]@{
        path = $identityPath
        bundle_plan_path = $identityPlanPath
        flavor_id = $identity.flavor_id
        target_id = $identity.target_id
        bundle_plan_sha256 = $identity.bundle_plan_sha256
        agent_lock_sha256 = $identity.agent_lock_sha256
        gate_ids = @($identity.gate_ids)
        source_revision = $identity.source_revision
        version = $identity.version
        project_wheels = @($identity.wheels | ForEach-Object { $_.filename })
    }
}
function Invoke-PackageAssemble {
    param(
        [System.Collections.IDictionary]$Context,
        [ref]$Report
    )

    Write-PackageLog "[assemble] Starting package assembly (profile: $($Context.profile))..."
    $hasGuiShell = @($Context.bundle_plan.shell_ids) -contains 'gui'
    if ($hasGuiShell) {
        Invoke-FrontendBuild -Context $Context -Report $Report
        if (@($Report.Value.blocking_issues).Count -gt 0) { return }
    }

    $identityTimer = New-PackageStageTimer
    try {
        $identitySummary = Invoke-ReleaseIdentity -Context $Context
        if ($identitySummary) {
            Add-StageResult -Report $Report -Name 'release_identity' -Status 'pass' -ExitCode 0 -Summary $identitySummary -StageTimer $identityTimer
        }
    }
    catch {
        Add-StageResult -Report $Report -Name 'release_identity' -Status 'fail' -ExitCode 1 -Summary @{ error = $_.Exception.Message } -StageTimer $identityTimer
        return
    }

    $guiLauncherExePath = ''
    if ($hasGuiShell) {
        $guiLauncherExePath = Invoke-GuiLauncherBuild -Context $Context -Report $Report
        if (@($Report.Value.blocking_issues).Count -gt 0) { return }
    }

    $preparePath = Resolve-ToolPath -Context $Context -RelativePath ([string]$Context.config.tooling.prepare_bundle)
    $buildPath = Resolve-ToolPath -Context $Context -RelativePath ([string]$Context.config.tooling.build_bundle)
    $requiredAssetIds = Get-PackageRequiredAssetIds -Context $Context
    $buildRoot = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.build_root)
    $assetCacheRoot = ''
    if ($Context.config.paths.PSObject.Properties.Name -contains 'asset_cache_root') {
        $assetCacheRoot = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.asset_cache_root)
    }
    $releaseIdentityPath = ''
    $reportsRoot = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.reports_root)
    $depsReportPath = Join-Path $reportsRoot 'deps.json'
    if ($Context.config.paths.PSObject.Properties.Name -contains 'release_identity') {
        $releaseIdentityPath = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.release_identity)
    }
    $prepareArgs = @(
        '-BuildRoot', $buildRoot,
        '-BundlePlanPath', [string]$Context.bundle_plan_path,
        '-BundlePlanSha256', [string]$Context.bundle_plan_sha256
    )
    if ($assetCacheRoot) {
        $prepareArgs += @('-AssetCacheRoot', $assetCacheRoot)
    }
    if ($releaseIdentityPath) {
        $prepareArgs += @('-ReleaseIdentityPath', $releaseIdentityPath)
    }
    if (@($requiredAssetIds).Count -gt 0) {
        $prepareArgs += '-AssetIds'
        $prepareArgs += ($requiredAssetIds -join ',')
    }
    if ([bool]$Context.allow_download) {
        $prepareArgs += '-AllowDownload'
    }
    if ($guiLauncherExePath) {
        $prepareArgs += '-GuiLauncherExePath'
        $prepareArgs += $guiLauncherExePath
    }
    $sitePackagesRoot = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.site_packages_root)
    if ($sitePackagesRoot -and (Test-Path -LiteralPath $sitePackagesRoot)) {
        $prepareArgs += '-SitePackagesRoot'
        $prepareArgs += $sitePackagesRoot
    }

    $buildArgs = @(
        '-ArtifactName', [string]$Context.artifact_name,
        '-BuildRoot', $buildRoot,
        '-BundlePlanPath', [string]$Context.bundle_plan_path,
        '-BundlePlanSha256', [string]$Context.bundle_plan_sha256
    )
    if ($assetCacheRoot) {
        $buildArgs += @('-AssetCacheRoot', $assetCacheRoot)
    }
    if ($releaseIdentityPath) {
        $buildArgs += @('-ReleaseIdentityPath', $releaseIdentityPath)
    }
    $buildArgs += @('-DepsReportPath', $depsReportPath)
    if (@($requiredAssetIds).Count -gt 0) {
        $buildArgs += '-AssetIds'
        $buildArgs += ($requiredAssetIds -join ',')
    }
    if ([bool]$Context.allow_download) {
        $buildArgs += '-AllowDownload'
    }

    Write-PackageLog "[assemble] Running prepare-offline.ps1..."
    $prepareTimer = New-PackageStageTimer
    try {
        $null = Invoke-StageScript -ProjectRoot $Context.project_root -ScriptPath $preparePath -Arguments $prepareArgs
    }
    catch {
        Write-PackageLog ("[assemble]   prepare FAILED: {0}" -f $_.Exception.Message)
        Add-StageResult -Report $Report -Name 'prepare' -Status 'fail' -ExitCode 1 -Summary @{ script = $preparePath; site_packages_root = $sitePackagesRoot; error = $_.Exception.Message } -StageTimer $prepareTimer
        return
    }
    Write-PackageLog "[assemble]   prepare OK"
    Add-StageResult -Report $Report -Name 'prepare' -Status 'pass' -ExitCode 0 -Summary @{ script = $preparePath; site_packages_root = $sitePackagesRoot } -StageTimer $prepareTimer

    Write-PackageLog "[assemble] Running build-offline-bundle.ps1..."
    $buildTimer = New-PackageStageTimer
    try {
        $null = Invoke-StageScript -ProjectRoot $Context.project_root -ScriptPath $buildPath -Arguments $buildArgs
    }
    catch {
        Write-PackageLog ("[assemble]   build FAILED: {0}" -f $_.Exception.Message)
        Add-StageResult -Report $Report -Name 'build' -Status 'fail' -ExitCode 1 -Summary @{ script = $buildPath; artifact_name = $Context.artifact_name; error = $_.Exception.Message } -StageTimer $buildTimer
        return
    }
    Write-PackageLog "[assemble]   build OK"
    Add-StageResult -Report $Report -Name 'build' -Status 'pass' -ExitCode 0 -Summary @{ script = $buildPath; artifact_name = $Context.artifact_name } -StageTimer $buildTimer

    Write-PackageLog "[assemble] Package assembly complete"
}

function Invoke-PackageLocalGate {
    param(
        [System.Collections.IDictionary]$Context,
        [ref]$Report,
        [string]$Name,
        [string]$ScriptPath,
        [string[]]$Arguments,
        [string]$ReportPath
    )

    $timer = New-PackageStageTimer
    $summary = @{ script = $ScriptPath; report = $ReportPath }
    try {
        $output = Invoke-StageScript -ProjectRoot $Context.project_root -ScriptPath $ScriptPath -Arguments $Arguments
        if ($ReportPath -and @($output).Count -gt 0) {
            $parent = Split-Path -Parent $ReportPath
            if (-not (Test-Path -LiteralPath $parent)) {
                New-Item -ItemType Directory -Path $parent -Force | Out-Null
            }
            Set-Content -LiteralPath $ReportPath -Value (($output -join "`n") + "`n") -Encoding UTF8
        }
        Add-StageResult -Report $Report -Name $Name -Status 'pass' -ExitCode 0 -Summary $summary -StageTimer $timer
        return $true
    }
    catch {
        $summary.error = $_.Exception.Message
        Add-StageResult -Report $Report -Name $Name -Status 'fail' -ExitCode 1 -Summary $summary -StageTimer $timer
        return $false
    }
}

function Invoke-PackageIdentityGate {
    param(
        [System.Collections.IDictionary]$Context,
        [System.Collections.IDictionary]$Report,
        [string]$BundleRoot,
        [string]$SourcesRoot
    )

    $timer = New-PackageStageTimer
    $bundleIdentity = Join-Path $BundleRoot 'manifests\release-identity.json'
    $sourceIdentity = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.release_identity)
    $summary = @{ bundle_identity = $bundleIdentity; source_identity = $sourceIdentity; sources_root = $SourcesRoot }
    try {
        if (-not (Test-Path -LiteralPath $bundleIdentity -PathType Leaf)) {
            throw 'bundle release identity is missing'
        }
        if (-not (Test-Path -LiteralPath $sourceIdentity -PathType Leaf)) {
            throw 'source release identity is missing'
        }
        $bundleHash = (Get-FileHash -LiteralPath $bundleIdentity -Algorithm SHA256).Hash.ToLowerInvariant()
        $sourceHash = (Get-FileHash -LiteralPath $sourceIdentity -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($bundleHash -ne $sourceHash) {
            throw 'bundle and source release identities differ'
        }
        $identity = Get-Content -LiteralPath $bundleIdentity -Raw | ConvertFrom-Json
        if (
            [int]$identity.schema_version -ne 2 -or
            [string]$identity.flavor_id -ne [string]$Context.bundle_plan.flavor_id -or
            [string]$identity.target_id -ne [string]$Context.bundle_plan.target_id -or
            [string]$identity.bundle_plan_sha256 -ne [string]$Context.bundle_plan_sha256 -or
            [string]$identity.agent_lock_sha256 -ne [string]$Context.bundle_plan.agent_lock_sha256 -or
            (@($identity.gate_ids) -join '|') -ne (@($Context.bundle_plan.gate_ids) -join '|')
        ) {
            throw 'release identity does not match the compiled bundle plan'
        }
        $evidencePlan = Join-Path $BundleRoot 'manifests\evidence\bundle-plan.json'
        if (-not (Test-Path -LiteralPath $evidencePlan -PathType Leaf)) {
            throw 'bundle evidence plan is missing'
        }
        $evidencePlanHash = (Get-FileHash -LiteralPath $evidencePlan -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($evidencePlanHash -ne [string]$Context.bundle_plan_sha256) {
            throw 'bundle evidence plan hash differs from the release identity'
        }
        $artifactHashesPath = Join-Path $SourcesRoot 'artifact-hashes.json'
        if (Test-Path -LiteralPath $artifactHashesPath -PathType Leaf) {
            $artifactHashes = Get-Content -LiteralPath $artifactHashesPath -Raw | ConvertFrom-Json
            if ($artifactHashes.identity_sha256 -and ([string]$artifactHashes.identity_sha256).ToLowerInvariant() -ne $bundleHash) {
                throw 'artifact-hashes identity_sha256 differs from the bundle identity'
            }
            if (
                [string]$artifactHashes.flavor_id -ne [string]$Context.bundle_plan.flavor_id -or
                [string]$artifactHashes.target_id -ne [string]$Context.bundle_plan.target_id -or
                [string]$artifactHashes.bundle_plan_sha256 -ne [string]$Context.bundle_plan_sha256 -or
                [string]$artifactHashes.agent_lock_sha256 -ne [string]$Context.bundle_plan.agent_lock_sha256 -or
                (@($artifactHashes.gate_ids) -join '|') -ne (@($Context.bundle_plan.gate_ids) -join '|')
            ) {
                throw 'artifact-hashes does not match the compiled bundle plan'
            }
        }
        $summary.identity_sha256 = $bundleHash
        Add-StageResult -Report $Report -Name 'identity_reproducibility' -Status 'pass' -ExitCode 0 -Summary $summary -StageTimer $timer
        return $true
    }
    catch {
        $summary.error = $_.Exception.Message
        Add-StageResult -Report $Report -Name 'identity_reproducibility' -Status 'fail' -ExitCode 1 -Summary $summary -StageTimer $timer
        return $false
    }
}

function Invoke-PackageZipExtractionGate {
    param(
        [System.Collections.IDictionary]$Context,
        [System.Collections.IDictionary]$Report,
        [string]$BundleRoot,
        [string]$SourcesRoot,
        [string]$ZipPath
    )

    $timer = New-PackageStageTimer
    $reportsRoot = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.reports_root)
    $validationScript = Resolve-ToolPath -Context $Context -RelativePath ([string]$Context.config.tooling.validate_bundle)
    $reportPath = Join-Path $reportsRoot 'zip-extracted-validate.json'
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('embedagent-zip-verify-' + [System.Guid]::NewGuid().ToString('N'))
    $summary = @{ zip = $ZipPath; extracted_root = $tempRoot; report = $reportPath }
    try {
        if (-not (Test-Path -LiteralPath $ZipPath -PathType Leaf)) {
            throw 'zip artifact is missing'
        }
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        [System.IO.Compression.ZipFile]::ExtractToDirectory($ZipPath, $tempRoot)
        $args = @(
            '-BundleRoot', $tempRoot,
            '-SourcesRoot', $SourcesRoot,
            '-ZipPath', $ZipPath,
            '-BundlePlanPath', [string]$Context.bundle_plan_path,
            '-BundlePlanSha256', [string]$Context.bundle_plan_sha256,
            '-SkipDynamicChecks',
            '-RequireComplete',
            '-JsonOutputPath', $reportPath
        )
        $null = Invoke-StageScript -ProjectRoot $Context.project_root -ScriptPath $validationScript -Arguments $args
        $payload = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
        if (-not $payload.ok) {
            throw 'zip-extracted bundle validation failed'
        }
        Add-StageResult -Report $Report -Name 'zip_extraction' -Status 'pass' -ExitCode 0 -Summary $summary -StageTimer $timer
        return $true
    }
    catch {
        $summary.error = $_.Exception.Message
        Add-StageResult -Report $Report -Name 'zip_extraction' -Status 'fail' -ExitCode 1 -Summary $summary -StageTimer $timer
        return $false
    }
    finally {
        if (Test-Path -LiteralPath $tempRoot) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}
function Remove-PostSmokeTransientArtifacts {
    param(
        [string]$BundleRoot
    )

    $cacheDirectories = @(
        Get-ChildItem -LiteralPath $BundleRoot -Recurse -Directory -Force -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -eq '__pycache__' } |
            Sort-Object FullName -Descending
    )
    foreach ($directory in $cacheDirectories) {
        Remove-Item -LiteralPath $directory.FullName -Recurse -Force
    }

    $cacheFiles = @(
        Get-ChildItem -LiteralPath $BundleRoot -Recurse -File -Force -ErrorAction SilentlyContinue |
            Where-Object { $_.Extension -in '.pyc', '.pyo' }
    )
    foreach ($file in $cacheFiles) {
        Remove-Item -LiteralPath $file.FullName -Force
    }

    $smokeBuildRoot = Join-Path $BundleRoot 'data\workspace-template\.embedagent\smoke-build'
    if (Test-Path -LiteralPath $smokeBuildRoot) {
        Remove-Item -LiteralPath $smokeBuildRoot -Recurse -Force
    }
}
function Invoke-PackageVerify {
    param(
        [System.Collections.IDictionary]$Context,
        [ref]$Report
    )

    Write-PackageLog "[verify] Starting bundle verification..."
    $bundleRoot = [string]$Context.artifact_root
    if (-not (Test-Path -LiteralPath $bundleRoot)) {
        Write-PackageLog ("[verify]   FAIL: Bundle root not found: {0}" -f $bundleRoot)
        Add-StageResult -Report $Report -Name 'verify' -Status 'fail' -ExitCode 1 -Summary @{ reason = 'bundle_root_missing'; bundle_root = $bundleRoot }
        return
    }

    $validateScript = Resolve-ToolPath -Context $Context -RelativePath ([string]$Context.config.tooling.validate_bundle)
    $checkScript = Resolve-ToolPath -Context $Context -RelativePath ([string]$Context.config.tooling.check_dependencies)
    $validateJson = New-ReportPath -Context $Context -StageName 'validate'
    $checkJson = New-ReportPath -Context $Context -StageName 'check'

    Write-PackageLog "[verify] Running validate-offline-bundle.ps1..."
    $verifyTimer = New-PackageStageTimer
    $validateArgs = @(
        '-BundleRoot', $bundleRoot,
        '-BundlePlanPath', [string]$Context.bundle_plan_path,
        '-BundlePlanSha256', [string]$Context.bundle_plan_sha256,
        '-JsonOutputPath', $validateJson
    )
    if (-not [bool]$Context.profile_config.run_dynamic_checks) {
        $validateArgs += '-SkipDynamicChecks'
    }
    if ([bool]$Context.profile_config.require_complete -or [bool]$Context.strict) {
        $validateArgs += '-RequireComplete'
    }
    try {
        $null = Invoke-StageScript -ProjectRoot $Context.project_root -ScriptPath $validateScript -Arguments $validateArgs
        $validatePayload = Get-Content -LiteralPath $validateJson -Raw | ConvertFrom-Json
        Write-PackageLog ("[verify]   validate: {0}" -f $(if ($validatePayload.ok) { "OK" } else { "FAIL" }))

        Write-PackageLog "[verify] Running check-bundle-dependencies.py..."
        $null = Invoke-StageScript -ProjectRoot $Context.project_root -ScriptPath $checkScript -Arguments @(
            $bundleRoot,
            '--bundle-plan', [string]$Context.bundle_plan_path,
            '--bundle-plan-sha256', [string]$Context.bundle_plan_sha256,
            '--json-report', $checkJson
        )
        $checkPayload = Get-Content -LiteralPath $checkJson -Raw | ConvertFrom-Json
        if (
            [string]$validatePayload.bundle_plan.sha256 -ne [string]$Context.bundle_plan_sha256 -or
            [string]$checkPayload.bundle_plan.sha256 -ne [string]$Context.bundle_plan_sha256
        ) {
            throw 'Bundle validation reports do not match the package plan hash.'
        }
        Write-PackageLog ("[verify]   dependencies: {0}" -f $(if ($checkPayload.ok) { "OK" } else { "FAIL" }))
    }
    catch {
        Add-StageResult -Report $Report -Name 'verify' -Status 'fail' -ExitCode 1 -Summary @{
            bundle_root = $bundleRoot
            validate_report = $validateJson
            dependency_report = $checkJson
            error = $_.Exception.Message
        } -StageTimer $verifyTimer
        return
    }

    $localGatesOk = $true
    $strictRelease = ($Context.config.paths.PSObject.Properties.Name -contains 'release_identity') -and [bool]$Context.profile_config.run_dynamic_checks
    if ($strictRelease) {
        $sourcesRoot = Join-Path (Split-Path -Parent $bundleRoot) ((Split-Path -Leaf $bundleRoot) + '-sources')
        if (-not (Invoke-PackageIdentityGate -Context $Context -Report $Report.Value -BundleRoot $bundleRoot -SourcesRoot $sourcesRoot)) {
            $localGatesOk = $false
        }
        $reportsRoot = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.reports_root)
        if (@($Context.bundle_plan.gate_ids) -contains 'gui_headless_smoke') {
            $guiScript = Join-Path $bundleRoot 'tools\validation\validate-gui-smoke.py'
            $guiReport = Join-Path $reportsRoot 'gui-smoke.json'
            if (-not (Invoke-PackageLocalGate -Context $Context -Report $Report -Name 'gui_headless_smoke' -ScriptPath $guiScript -Arguments @('--bundle-root', $bundleRoot, '--require-fixed-webview2') -ReportPath $guiReport)) {
                $localGatesOk = $false
            }
        }
        if (@($Context.bundle_plan.gate_ids) -contains 'cpp_smoke_workspace') {
            $cppScript = Join-Path $bundleRoot 'tools\validation\validate-cpp-smoke.py'
            $cppReport = Join-Path $reportsRoot 'cpp-smoke.json'
            if (-not (Invoke-PackageLocalGate -Context $Context -Report $Report -Name 'cpp_smoke' -ScriptPath $cppScript -Arguments @('--bundle-root', $bundleRoot, '--json-report', $cppReport) -ReportPath $cppReport)) {
                $localGatesOk = $false
            }
        }
        try {
            Remove-PostSmokeTransientArtifacts -BundleRoot $bundleRoot
        }
        catch {
            Write-PackageLog ("[verify]   transient cleanup FAILED: {0}" -f $_.Exception.Message)
            $localGatesOk = $false
        }
        $zipPath = Join-Path (Split-Path -Parent $bundleRoot) ((Split-Path -Leaf $bundleRoot) + '.zip')
        if (-not (Invoke-PackageZipExtractionGate -Context $Context -Report $Report.Value -BundleRoot $bundleRoot -SourcesRoot $sourcesRoot -ZipPath $zipPath)) {
            $localGatesOk = $false
        }
    }
$verifyOk = ([bool]$validatePayload.ok) -and ([bool]$checkPayload.ok) -and $localGatesOk
    Add-StageResult -Report $Report -Name 'verify' -Status $(if ($verifyOk) { 'pass' } else { 'fail' }) -ExitCode $(if ($verifyOk) { 0 } else { 1 }) -Summary @{
        bundle_root = $bundleRoot
        validate_report = $validateJson
        dependency_report = $checkJson
    } -StageTimer $verifyTimer
    Write-PackageLog ("[verify] Overall: {0}" -f $(if ($verifyOk) { "PASS" } else { "FAIL" }))
}

function Write-AtomicPackageText {
    param(
        [string]$Path,
        [string]$Content,
        [System.Text.Encoding]$Encoding
    )

    $temporaryPath = $Path + ".tmp." + [guid]::NewGuid().ToString('N')
    try {
        [System.IO.File]::WriteAllText($temporaryPath, $Content, $Encoding)
        Move-Item -LiteralPath $temporaryPath -Destination $Path -Force
    }
    finally {
        if (Test-Path -LiteralPath $temporaryPath) {
            Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
        }
    }
}

function Write-PackageReport {
    param(
        [System.Collections.IDictionary]$Context,
        [System.Collections.IDictionary]$Report
    )

    $reportsRoot = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.reports_root)
    if (-not (Test-Path -LiteralPath $reportsRoot)) {
        New-Item -ItemType Directory -Path $reportsRoot -Force | Out-Null
    }
    $timestamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddHHmmss')
    $reportPath = Join-Path $reportsRoot ($timestamp + '-' + $Context.run_id + '-' + $Context.command + '.json')
    $latestPath = Join-Path $reportsRoot 'latest.json'
    $Report.report_path = $reportPath
    $Report.generated_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    $json = $Report | ConvertTo-Json -Depth 10
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    Write-AtomicPackageText -Path $reportPath -Content $json -Encoding $utf8NoBom
    Write-AtomicPackageText -Path $latestPath -Content $json -Encoding $utf8NoBom
    return $reportPath
}

function New-ReproducibilityRunConfig {
    param(
        [System.Collections.IDictionary]$Context,
        [string]$RunRoot
    )

    New-Item -ItemType Directory -Path $RunRoot -Force | Out-Null
    $config = ($Context.config | ConvertTo-Json -Depth 20) | ConvertFrom-Json
    $buildRoot = Join-Path $RunRoot 'build'
    $reportsRoot = Join-Path $RunRoot 'reports'
    $exportRoot = Join-Path $RunRoot 'site-packages-export'
    $artifactName = [string]$Context.artifact_name
    $bundleRoot = Join-Path $buildRoot (Join-Path 'offline-dist' $artifactName)
    $assetCacheRoot = if ($Context.config.paths.PSObject.Properties.Name -contains 'asset_cache_root') {
        Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.asset_cache_root)
    }
    else {
        Join-Path $Context.project_root 'build\offline-cache'
    }

    $config.metadata.config_origin = 'production'
    $config.default_profile = 'release'
    $config.paths.build_root = $buildRoot
    $config.paths.reports_root = $reportsRoot
    $config.paths.site_packages_export_root = $exportRoot
    $config.paths.site_packages_root = Join-Path $exportRoot 'site-packages'
    $config.paths.gui_launcher_build_root = Join-Path $RunRoot 'gui-launcher'
    $config.paths.dist_bundle_root = $bundleRoot
    if ($config.paths.PSObject.Properties.Name -contains 'asset_cache_root') {
        $config.paths.asset_cache_root = $assetCacheRoot
    }
    else {
        $config.paths | Add-Member -NotePropertyName asset_cache_root -NotePropertyValue $assetCacheRoot
    }
    if ($config.paths.PSObject.Properties.Name -contains 'release_identity') {
        $config.paths.release_identity = Join-Path $RunRoot 'release-identity.json'
    }
    if ($config.paths.PSObject.Properties.Name -contains 'release_evidence_root') {
        $config.paths.release_evidence_root = Join-Path $RunRoot 'evidence'
    }

    $configPath = Join-Path $RunRoot 'package.config.json'
    $json = $config | ConvertTo-Json -Depth 20
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    Write-AtomicPackageText -Path $configPath -Content $json -Encoding $utf8NoBom
    return [ordered]@{
        config_path = $configPath
        reports_root = $reportsRoot
        bundle_root = $bundleRoot
    }
}

function Invoke-ReproducibilityChildRelease {
    param(
        [System.Collections.IDictionary]$Context,
        [System.Collections.IDictionary]$Run
    )

    $powerShellPath = Resolve-PackagePowerShellPath
    $packageScript = Join-Path $Context.project_root 'scripts\package.ps1'
    $arguments = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', $packageScript,
        'release',
        '-Profile', 'release',
        '-Flavor', [string]$Context.flavor,
        '-Config', [string]$Run.config_path,
        '-Json'
    )
    $output = & $powerShellPath @arguments 2>&1
    $exitCode = $LASTEXITCODE
    $payload = $null
    try {
        $payload = (($output | Out-String).Trim()) | ConvertFrom-Json
    }
    catch {
        $payload = $null
    }
    return [ordered]@{
        exit_code = $exitCode
        report = $payload
        report_path = $(if ($payload -and $payload.report_path) { [string]$payload.report_path } else { '' })
        bundle_root = [string]$Run.bundle_root
    }
}

function Test-ReproducibilityChildEligible {
    param(
        [System.Collections.IDictionary]$Child
    )

    if ($Child.exit_code -ne 0 -or -not $Child.report) {
        return $false
    }
    return (
        $Child.report.execution_kind -eq 'release' -and
        $Child.report.config_origin -eq 'production' -and
        $Child.report.profile -eq 'release' -and
        $Child.report.final_status -in @('READY', 'TARGET_READY')
    )
}

function Invoke-PackageReproducibility {
    param(
        [System.Collections.IDictionary]$Context
    )

    $report = New-PackageContextReport -Context $Context
    $timer = New-PackageStageTimer
    $baseRoot = if ($Context.reproducibility_root) {
        Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.reproducibility_root)
    }
    else {
        Join-Path $Context.project_root 'build\release-reproducibility'
    }
    $executionRoot = Join-Path $baseRoot ([string]$Context.run_id)
    $firstRun = New-ReproducibilityRunConfig -Context $Context -RunRoot (Join-Path $executionRoot 'run-a')
    $secondRun = New-ReproducibilityRunConfig -Context $Context -RunRoot (Join-Path $executionRoot 'run-b')
    $firstChild = Invoke-ReproducibilityChildRelease -Context $Context -Run $firstRun
    $secondChild = Invoke-ReproducibilityChildRelease -Context $Context -Run $secondRun
    $comparisonPath = Join-Path $executionRoot 'artifact-reproducibility.json'
    $mismatches = @()
    $comparison = $null

    if (-not (Test-ReproducibilityChildEligible -Child $firstChild)) {
        $mismatches += 'child.run-a.not_ready'
    }
    if (-not (Test-ReproducibilityChildEligible -Child $secondChild)) {
        $mismatches += 'child.run-b.not_ready'
    }
    if ($mismatches.Count -eq 0) {
        $compareScript = Join-Path $Context.project_root 'scripts\compare-release-artifacts.py'
        try {
            $null = Invoke-StageScript -ProjectRoot $Context.project_root -ScriptPath $compareScript -Arguments @(
                '--first-report', [string]$firstChild.report_path,
                '--second-report', [string]$secondChild.report_path,
                '--first-root', [string]$firstChild.bundle_root,
                '--second-root', [string]$secondChild.bundle_root,
                '--json-report', $comparisonPath
            )
        }
        catch {
            # The comparison report is authoritative even when the comparator returns 1.
        }
        if (Test-Path -LiteralPath $comparisonPath -PathType Leaf) {
            $comparison = Get-Content -LiteralPath $comparisonPath -Raw | ConvertFrom-Json
            $mismatches = @($comparison.mismatches)
        }
        else {
            $mismatches = @('comparison.report_missing')
        }
    }

    $summary = [ordered]@{
        execution_root = $executionRoot
        first_report = [string]$firstChild.report_path
        second_report = [string]$secondChild.report_path
        first_bundle_root = [string]$firstChild.bundle_root
        second_bundle_root = [string]$secondChild.bundle_root
        comparison_report = $comparisonPath
        first_bundle_sha256 = $(if ($comparison) { $comparison.first_bundle_sha256 } else { $null })
        second_bundle_sha256 = $(if ($comparison) { $comparison.second_bundle_sha256 } else { $null })
        mismatches = @($mismatches)
        excluded_paths = $(if ($comparison) { @($comparison.excluded_paths) } else { @() })
    }
    $ok = ($mismatches.Count -eq 0)
    Add-StageResult -Report ([ref]$report) -Name 'artifact_reproducibility' -Status $(if ($ok) { 'pass' } else { 'fail' }) -ExitCode $(if ($ok) { 0 } else { 1 }) -Summary $summary -StageTimer $timer
    Complete-PackageReport -Report ([ref]$report)
    if ($ok -and $Context.execution_kind -eq 'release' -and $Context.config_origin -eq 'production' -and $Context.profile -eq 'release') {
        $report.final_status = 'TARGET_READY'
        $report.release_state = 'TARGET_READY'
        $report.acceptance_status = 'PENDING_WIN7'
        $report.artifact_status = 'target-ready'
        $report.publishable = $false
        $report.artifact_root = [string]$secondChild.bundle_root
        $report.evidence_root = Join-Path ([string]$secondChild.bundle_root) 'manifests\evidence'
    }
    $null = Write-PackageReport -Context $Context -Report $report
    return $report
}
function Invoke-PackageCommand {
    param(
        [System.Collections.IDictionary]$Context
    )

    Write-PackageLog ""
    Write-PackageLog ("=== Package Command: {0} (profile: {1}, flavor: {2}) ===" -f $Context.command, $Context.profile, $Context.flavor)
    $report = New-PackageContextReport -Context $Context
    switch ($Context.command) {
        'deps' {
            Invoke-PackageDeps -Context $Context -Report ([ref]$report)
        }
        'assemble' {
            Invoke-PackageAssemble -Context $Context -Report ([ref]$report)
        }
        'verify' {
            Invoke-PackageVerify -Context $Context -Report ([ref]$report)
        }
        'release' {
            Invoke-PackageDeps -Context $Context -Report ([ref]$report)
            if (@($report.blocking_issues).Count -eq 0) {
                Invoke-PackageAssemble -Context $Context -Report ([ref]$report)
            }
            if (@($report.blocking_issues).Count -eq 0) {
                Invoke-PackageVerify -Context $Context -Report ([ref]$report)
            }
        }
        default {
            throw "Unsupported packaging command: $($Context.command)"
        }
    }
    Complete-PackageReport -Report ([ref]$report)
    $identityConfigured = $Context.config.paths.PSObject.Properties.Name -contains 'release_identity'
    if ($identityConfigured -and ($Context.execution_kind -ne 'release' -or $Context.config_origin -ne 'production' -or $Context.profile -ne 'release')) {
        $identityConfigured = $false
    }
    if ($identityConfigured -and $report.final_status -eq 'READY') {
        $report.final_status = 'TARGET_READY'
        $report.release_state = 'TARGET_READY'
        $report.acceptance_status = 'PENDING_WIN7'
        $report.artifact_status = 'target-ready'
        $report.publishable = $false
        $targetBundleRoot = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.dist_bundle_root)
        $report.evidence_root = Join-Path $targetBundleRoot 'manifests\evidence'
    }
    $null = Write-PackageReport -Context $Context -Report $report
    $statusStr = $report.command_status
    if ($report.final_status) {
        $statusStr = $report.final_status
    }
    Write-PackageLog ("=== Command finished: {0} ===" -f $statusStr)
    Write-PackageLog ""
    return $report
}
