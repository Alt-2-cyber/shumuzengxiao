# Run the real wrapper with every process and Storage command replaced by Pester.
$script:wrapperPath = Join-Path $PSScriptRoot 'apply-maixcam-card-patch.ps1'
$script:adapterPath = Join-Path $PSScriptRoot 'maixcam_apply_card_patch.py'
$tokens = $null
$parseErrors = $null
$wrapperAst = [System.Management.Automation.Language.Parser]::ParseFile(
    $script:wrapperPath, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw 'The card wrapper does not parse.' }
$pythonAssignments = @($wrapperAst.FindAll({
    param($node)
    $node -is [System.Management.Automation.Language.AssignmentStatementAst] -and
        $node.Left -is [System.Management.Automation.Language.VariableExpressionAst] -and
        $node.Left.VariablePath.UserPath -eq 'python'
}, $true))
if ($pythonAssignments.Count -ne 1) { throw 'Expected one Python process boundary.' }
$pythonLiteral = $pythonAssignments[0].Right.Find({
    param($node)
    $node -is [System.Management.Automation.Language.StringConstantExpressionAst]
}, $true)
if ($null -eq $pythonLiteral) { throw 'The Python process boundary must be a literal path.' }
$script:pythonBoundary = $pythonLiteral.Value

# These fail-closed functions shadow real commands even if a Pester mock is lost.
function Get-Disk {
    param([int]$Number)
    throw 'An unmocked Get-Disk call was blocked by the test.'
}
function Get-Partition {
    param([int]$DiskNumber, [int]$PartitionNumber)
    throw 'An unmocked Get-Partition call was blocked by the test.'
}
function Set-Disk {
    param([int]$Number, [bool]$IsOffline)
    throw 'An unmocked Set-Disk call was blocked by the test.'
}
Set-Item -LiteralPath ('Function:\script:' + $script:pythonBoundary) -Value {
    throw 'An unmocked Python process launch was blocked by the test.'
}

function Invoke-CardWrapperFixture {
    param([switch]$UseVolumeLock)
    if ((Get-Command -Name $script:pythonBoundary).CommandType -ne 'Function') {
        throw 'The native Python process is not intercepted.'
    }
    $state = $global:MaixcamCardWrapperTestState
    $state.ExpectedVolumeLock = [bool]$UseVolumeLock
    & $script:wrapperPath -DescriptorPath $state.DescriptorPath `
        -BackupSummary $state.BackupPath -PlanPath $state.PlanPath `
        -OutputDirectory $state.OutputPath -UseVolumeLock:$UseVolumeLock 3>$null
}

Describe 'MaixCAM card wrapper with no physical I/O' {
    BeforeEach {
        # Pester 3 invokes mocks from the called script's scope. Keep shared
        # fixture state in a named global, removed by AfterAll, rather than $script:.
        $global:MaixcamCardWrapperTestState = @{
            FixturePath = Join-Path $TestDrive ([guid]::NewGuid().ToString('N'))
            AdapterPath = $script:adapterPath
            DeviceOffline = $false
            InitialDisk = @{
                Number = 12345
                Size = 16384
                BusType = 'USB'
                UniqueId = 'maixcam-test-unique-id'
                SerialNumber = 'maixcam-test-serial'
            }
            ChangedIdentity = @{}
            PartitionOffset = 4096
            ExpectedVolumeLock = $false
            BootVolume = '\\?\Volume{11111111-2222-3333-4444-555555555555}'
            BootOffset = 512
            BootSize = 3584
            ProcessCode = 0
            ProcessThrows = $false
            WriteResult = $true
            ResultPhase = 'complete'
            StartupVerified = $true
            DiskCalls = 0
            Events = New-Object 'System.Collections.Generic.List[string]'
        }
        $state = $global:MaixcamCardWrapperTestState
        New-Item -ItemType Directory -Path $state.FixturePath | Out-Null
        $state.DescriptorPath = Join-Path $state.FixturePath 'descriptor.json'
        $state.BackupPath = Join-Path $state.FixturePath 'backup.json'
        $state.PlanPath = Join-Path $state.FixturePath 'plan.json'
        $state.OutputPath = Join-Path $state.FixturePath 'output'
        $state.BootAccessPaths = @('E:\', ($state.BootVolume + '\'))
        @{
            disk_number = 12345
            disk_size = 16384
            partition_offset = 4096
            partition_size = 8192
            bus_type = 'USB'
            maixcam_boot_verified = $true
        } | ConvertTo-Json | Set-Content -LiteralPath $state.DescriptorPath -Encoding UTF8
        '{}' | Set-Content -LiteralPath $state.BackupPath -Encoding UTF8
        '{}' | Set-Content -LiteralPath $state.PlanPath -Encoding UTF8
        $global:LASTEXITCODE = 99

        Mock Get-Disk {
            $state = $global:MaixcamCardWrapperTestState
            if ($Number -ne 12345) { throw 'The test only permits nonexistent disk 12345.' }
            $state.DiskCalls++
            $snapshot = @{}
            foreach ($key in $state.InitialDisk.Keys) { $snapshot[$key] = $state.InitialDisk[$key] }
            if ($state.DiskCalls -gt 1) {
                foreach ($key in $state.ChangedIdentity.Keys) {
                    $snapshot[$key] = $state.ChangedIdentity[$key]
                }
            }
            $snapshot.IsOffline = $state.DeviceOffline
            [pscustomobject]$snapshot
        }
        Mock Get-Partition {
            $state = $global:MaixcamCardWrapperTestState
            if ($DiskNumber -ne 12345 -or $PartitionNumber -notin @(1, 2)) {
                throw 'The test only permits partitions 1 and 2 of nonexistent disk 12345.'
            }
            if ($PartitionNumber -eq 1) {
                return [pscustomobject]@{
                    Offset = $state.BootOffset
                    Size = $state.BootSize
                    AccessPaths = $state.BootAccessPaths
                }
            }
            [pscustomobject]@{ Offset = $state.PartitionOffset; Size = 8192 }
        }
        Mock Set-Disk {
            $state = $global:MaixcamCardWrapperTestState
            if ($Number -ne 12345) { throw 'A real disk number was blocked by the test.' }
            $state.DeviceOffline = [bool]$IsOffline
            if ($IsOffline) { $state.Events.Add('offline') }
            else { $state.Events.Add('online') }
        }
        Mock $script:pythonBoundary {
            $state = $global:MaixcamCardWrapperTestState
            $arguments = @($args)
            if ($state.ExpectedVolumeLock) {
                if ($state.DeviceOffline) { throw 'Volume locking must leave the fixture disk online.' }
                if ($arguments.Count -ne 13 -or $arguments[11] -ne '--boot-volume' -or
                    $arguments[12] -cne $state.BootVolume) {
                    throw 'The wrapper did not pass the unique volume GUID without a trailing slash.'
                }
            } elseif (-not $state.DeviceOffline -or $arguments.Count -ne 11) {
                throw 'The default branch must take the disk offline without adding volume arguments.'
            }
            if ($arguments[0] -ne '-u' -or
                $arguments[1] -ne $state.AdapterPath -or
                $arguments[2] -ne '--descriptor' -or $arguments[3] -ne $state.DescriptorPath -or
                $arguments[4] -ne '--backup-summary' -or $arguments[5] -ne $state.BackupPath -or
                $arguments[6] -ne '--plan' -or $arguments[7] -ne $state.PlanPath -or
                $arguments[8] -ne '--output' -or $arguments[9] -ne $state.OutputPath -or
                $arguments[10] -ne '--apply') {
                throw 'Unexpected adapter process arguments.'
            }
            $descriptor = Get-Content -LiteralPath $state.DescriptorPath -Raw | ConvertFrom-Json
            if ($descriptor.disk_number -ne 12345) { throw 'A nonfixture descriptor was blocked.' }
            $state.Events.Add('process')
            if ($state.ProcessThrows) { throw 'Injected process launch failure.' }
            if ($state.WriteResult) {
                @{
                    phase = $state.ResultPhase
                    startup_files_verified = $state.StartupVerified
                } | ConvertTo-Json | Set-Content -LiteralPath (
                    Join-Path $state.OutputPath 'apply-result.json') -Encoding UTF8
            }
            $global:LASTEXITCODE = $state.ProcessCode
        }
    }

    It 'restores an originally online disk only after verified process success' {
        Invoke-CardWrapperFixture
        $global:LASTEXITCODE | Should Be 0
        ($global:MaixcamCardWrapperTestState.Events -join ',') | Should Be 'offline,process,online'
        $global:MaixcamCardWrapperTestState.DeviceOffline | Should Be $false
        Assert-MockCalled Get-Disk -Times 2 -Exactly -Scope It
        Assert-MockCalled Get-Partition -Times 1 -Exactly -Scope It
        Assert-MockCalled $script:pythonBoundary -Times 1 -Exactly -Scope It
        Assert-MockCalled Set-Disk -Times 1 -Exactly -Scope It -ParameterFilter { $IsOffline -eq $false }
    }

    It 'keeps the disk offline when the adapter exits with failure' {
        $global:MaixcamCardWrapperTestState.ProcessCode = 7
        $global:MaixcamCardWrapperTestState.ResultPhase = 'failed'
        $global:MaixcamCardWrapperTestState.StartupVerified = $false
        Invoke-CardWrapperFixture
        $global:LASTEXITCODE | Should Be 7
        ($global:MaixcamCardWrapperTestState.Events -join ',') | Should Be 'offline,process'
        $global:MaixcamCardWrapperTestState.DeviceOffline | Should Be $true
        Assert-MockCalled Set-Disk -Times 0 -Exactly -Scope It -ParameterFilter { $IsOffline -eq $false }
    }

    It 'does not trust a complete result when the adapter exit code is nonzero' {
        $global:MaixcamCardWrapperTestState.ProcessCode = 9
        Invoke-CardWrapperFixture
        $global:LASTEXITCODE | Should Be 9
        $global:MaixcamCardWrapperTestState.DeviceOffline | Should Be $true
        Assert-MockCalled Set-Disk -Times 0 -Exactly -Scope It -ParameterFilter { $IsOffline -eq $false }
    }

    It 'preserves an originally offline disk after verified success' {
        $global:MaixcamCardWrapperTestState.DeviceOffline = $true
        Invoke-CardWrapperFixture
        $global:LASTEXITCODE | Should Be 0
        ($global:MaixcamCardWrapperTestState.Events -join ',') | Should Be 'process'
        $global:MaixcamCardWrapperTestState.DeviceOffline | Should Be $true
        Assert-MockCalled Set-Disk -Times 0 -Exactly -Scope It
        Assert-MockCalled Get-Disk -Times 1 -Exactly -Scope It
        Assert-MockCalled $script:pythonBoundary -Times 1 -Exactly -Scope It
    }

    It 'keeps the disk offline when no result file was produced' {
        $global:MaixcamCardWrapperTestState.WriteResult = $false
        Invoke-CardWrapperFixture
        $global:MaixcamCardWrapperTestState.DeviceOffline | Should Be $true
        Assert-MockCalled Set-Disk -Times 0 -Exactly -Scope It -ParameterFilter { $IsOffline -eq $false }
    }

    It 'keeps the disk offline when the result phase is not complete' {
        $global:MaixcamCardWrapperTestState.ResultPhase = 'failed'
        Invoke-CardWrapperFixture
        $global:MaixcamCardWrapperTestState.DeviceOffline | Should Be $true
        Assert-MockCalled Set-Disk -Times 0 -Exactly -Scope It -ParameterFilter { $IsOffline -eq $false }
    }

    It 'keeps the disk offline when startup verification is false' {
        $global:MaixcamCardWrapperTestState.StartupVerified = $false
        Invoke-CardWrapperFixture
        $global:MaixcamCardWrapperTestState.DeviceOffline | Should Be $true
        Assert-MockCalled Set-Disk -Times 0 -Exactly -Scope It -ParameterFilter { $IsOffline -eq $false }
    }

    It 'keeps the disk offline if launching the adapter throws' {
        $global:MaixcamCardWrapperTestState.ProcessThrows = $true
        { Invoke-CardWrapperFixture } | Should Throw 'Injected process launch failure'
        $global:MaixcamCardWrapperTestState.DeviceOffline | Should Be $true
        Assert-MockCalled Set-Disk -Times 0 -Exactly -Scope It -ParameterFilter { $IsOffline -eq $false }
    }

    It 'refuses to online a disk whose UniqueId changed' {
        $global:MaixcamCardWrapperTestState.ChangedIdentity.UniqueId = 'different-fixture-id'
        { Invoke-CardWrapperFixture } | Should Throw 'Camera disk identity changed'
        $global:MaixcamCardWrapperTestState.DeviceOffline | Should Be $true
        Assert-MockCalled Set-Disk -Times 0 -Exactly -Scope It -ParameterFilter { $IsOffline -eq $false }
    }

    It 'refuses to online a disk whose size changed' {
        $global:MaixcamCardWrapperTestState.ChangedIdentity.Size = 32768
        { Invoke-CardWrapperFixture } | Should Throw 'Camera disk identity changed'
        $global:MaixcamCardWrapperTestState.DeviceOffline | Should Be $true
        Assert-MockCalled Set-Disk -Times 0 -Exactly -Scope It -ParameterFilter { $IsOffline -eq $false }
    }

    It 'refuses to online a disk whose bus type changed' {
        $global:MaixcamCardWrapperTestState.ChangedIdentity.BusType = 'SATA'
        { Invoke-CardWrapperFixture } | Should Throw 'Camera disk identity changed'
        $global:MaixcamCardWrapperTestState.DeviceOffline | Should Be $true
        Assert-MockCalled Set-Disk -Times 0 -Exactly -Scope It -ParameterFilter { $IsOffline -eq $false }
    }

    It 'refuses to online a disk whose serial number changed' {
        $global:MaixcamCardWrapperTestState.ChangedIdentity.SerialNumber = 'different-fixture-serial'
        { Invoke-CardWrapperFixture } | Should Throw 'Camera disk identity changed'
        $global:MaixcamCardWrapperTestState.DeviceOffline | Should Be $true
        Assert-MockCalled Set-Disk -Times 0 -Exactly -Scope It -ParameterFilter { $IsOffline -eq $false }
    }

    It 'rejects an unexpected partition before changing disk state or starting Python' {
        $global:MaixcamCardWrapperTestState.PartitionOffset = 4608
        { Invoke-CardWrapperFixture } | Should Throw 'The camera partition layout changed'
        Assert-MockCalled Set-Disk -Times 0 -Exactly -Scope It
        Assert-MockCalled $script:pythonBoundary -Times 0 -Exactly -Scope It
    }

    It 'passes the unique boot volume to the adapter without any Set-Disk calls' {
        Invoke-CardWrapperFixture -UseVolumeLock
        $global:LASTEXITCODE | Should Be 0
        ($global:MaixcamCardWrapperTestState.Events -join ',') | Should Be 'process'
        $global:MaixcamCardWrapperTestState.DeviceOffline | Should Be $false
        Assert-MockCalled Set-Disk -Times 0 -Exactly -Scope It
        Assert-MockCalled Get-Partition -Times 1 -Exactly -Scope It -ParameterFilter { $PartitionNumber -eq 1 }
        Assert-MockCalled Get-Partition -Times 1 -Exactly -Scope It -ParameterFilter { $PartitionNumber -eq 2 }
        Assert-MockCalled $script:pythonBoundary -Times 1 -Exactly -Scope It
    }

    It 'preserves the adapter failure code without trying to offline removable media' {
        $global:MaixcamCardWrapperTestState.ProcessCode = 7
        $global:MaixcamCardWrapperTestState.ResultPhase = 'failed'
        $global:MaixcamCardWrapperTestState.StartupVerified = $false
        Invoke-CardWrapperFixture -UseVolumeLock
        $global:LASTEXITCODE | Should Be 7
        ($global:MaixcamCardWrapperTestState.Events -join ',') | Should Be 'process'
        Assert-MockCalled Set-Disk -Times 0 -Exactly -Scope It
        Assert-MockCalled $script:pythonBoundary -Times 1 -Exactly -Scope It
    }

    It 'does not change disk state when the volume lock process launch throws' {
        $global:MaixcamCardWrapperTestState.ProcessThrows = $true
        { Invoke-CardWrapperFixture -UseVolumeLock } | Should Throw 'Injected process launch failure'
        Assert-MockCalled Set-Disk -Times 0 -Exactly -Scope It
    }

    It 'rejects a drive letter instead of a volume GUID before launching the adapter' {
        $global:MaixcamCardWrapperTestState.BootAccessPaths = @('E:\')
        { Invoke-CardWrapperFixture -UseVolumeLock } | Should Throw 'boot volume identity is not available'
        Assert-MockCalled Set-Disk -Times 0 -Exactly -Scope It
        Assert-MockCalled $script:pythonBoundary -Times 0 -Exactly -Scope It
    }

    It 'rejects ambiguous volume GUIDs before launching the adapter' {
        $state = $global:MaixcamCardWrapperTestState
        $state.BootAccessPaths = @(
            ($state.BootVolume + '\'),
            '\\?\Volume{aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee}\'
        )
        { Invoke-CardWrapperFixture -UseVolumeLock } | Should Throw 'boot volume identity is not available'
        Assert-MockCalled Set-Disk -Times 0 -Exactly -Scope It
        Assert-MockCalled $script:pythonBoundary -Times 0 -Exactly -Scope It
    }

    It 'rejects a boot extent overlapping Linux before launching the adapter' {
        $global:MaixcamCardWrapperTestState.BootSize = 4096
        { Invoke-CardWrapperFixture -UseVolumeLock } | Should Throw 'boot volume identity is not available'
        Assert-MockCalled Set-Disk -Times 0 -Exactly -Scope It
        Assert-MockCalled $script:pythonBoundary -Times 0 -Exactly -Scope It
    }

    It 'rejects volume locking for a disk that was already offline' {
        $global:MaixcamCardWrapperTestState.DeviceOffline = $true
        { Invoke-CardWrapperFixture -UseVolumeLock } | Should Throw 'Volume locking requires'
        $global:MaixcamCardWrapperTestState.DeviceOffline | Should Be $true
        Assert-MockCalled Set-Disk -Times 0 -Exactly -Scope It
        Assert-MockCalled $script:pythonBoundary -Times 0 -Exactly -Scope It
    }

    AfterAll {
        Remove-Item -LiteralPath ('Function:\script:' + $script:pythonBoundary) -ErrorAction SilentlyContinue
        Remove-Variable -Name MaixcamCardWrapperTestState -Scope Global -ErrorAction SilentlyContinue
    }
}
