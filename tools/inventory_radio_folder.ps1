<#
.SYNOPSIS
    Inventory and triage a ham-radio folder for CQ WW contest material.

.DESCRIPTION
    Walks a folder tree, classifies every file by CONTENT (not extension alone),
    and writes a CSV manifest plus a summary. Optionally stages the files worth
    keeping into a flat folder ready to commit to the BFA repo.

    Written for a OneDrive-backed ham-radio folder tree.

    Classifies into:
      CABRILLO      a contest log (START-OF-LOG). Extracts CALLSIGN, CONTEST,
                    year and QSO count - this is the triage that matters.
      LCR_UBN       a CQ log-checking report (the highest-value item).
      ADIF          general logbook export.
      N1MM_DB       N1MM contest database (.s3db).
      CTY           an AD1C country file (extracts its VER string).
      SCP           super check partial callsign list.
      CALLHISTORY   N1MM call-history file.
      OTHER         everything else, listed but not staged.

.PARAMETER Path
    Root folder to inventory.

.PARAMETER OutCsv
    Where to write the manifest CSV.

.PARAMETER StageTo
    Optional. Copy classified contest material into this folder, organised by
    type, ready to commit.

.PARAMETER HydrateCloudFiles
    OneDrive files may be online-only placeholders. Reading one forces a
    download. By default those are listed and SKIPPED rather than silently
    pulling gigabytes. Pass this to download and classify them too.

.EXAMPLE
    .\inventory_radio_folder.ps1 -Path "D:\Radio"

.EXAMPLE
    .\inventory_radio_folder.ps1 `
        -Path "D:\Radio" `
        -StageTo "C:\temp\bfa-stage" -HydrateCloudFiles
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Path,
    # Bug 4: the manifest lists every filename in the tree, which can include
    # passport and booking scans. It must never default into a repo checkout.
    [string]$OutCsv = (Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'bfa\radio_inventory.csv'),
    [string]$StageTo = "",
    [switch]$HydrateCloudFiles
)

$ErrorActionPreference = 'Continue'

if (-not (Test-Path -LiteralPath $Path)) {
    Write-Error "Path not found: $Path"
    exit 1
}

Write-Host "Scanning $Path ..." -ForegroundColor Cyan

# FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x400000 -> OneDrive online-only placeholder
$RECALL = 0x400000

# Bug 1: binaries (.wav .pdf .zip .chm .DB .DOC) decoded as ASCII produced 24
# false LCR_UBN hits out of 26. Never content-sniff a file containing NUL bytes,
# and never sniff a known-binary extension at all.
$BinaryExt = @('.wav','.mp3','.mp4','.avi','.jpg','.jpeg','.png','.gif','.bmp','.tif','.tiff',
               '.pdf','.zip','.rar','.7z','.gz','.tar','.cab','.chm','.exe','.dll','.msi',
               '.doc','.docx','.xls','.xlsx','.ppt','.pptx','.db','.mdb','.accdb','.bin',
               '.iso','.dmg','.wav','.ogg','.flac','.psd','.ico')

function Get-Head {
    <# Returns ASCII head, or $null when the file is binary or unreadable. #>
    param([string]$File, [int]$Bytes = 8192)
    try {
        $fs = [System.IO.File]::Open($File, 'Open', 'Read', 'ReadWrite')
        try {
            $len = [Math]::Min($Bytes, $fs.Length)
            if ($len -eq 0) { return '' }
            $buf = New-Object byte[] $len
            [void]$fs.Read($buf, 0, $len)
            # A NUL byte in the head means binary. Text logs never contain one.
            if ([Array]::IndexOf($buf, [byte]0) -ge 0) { return $null }
            return [System.Text.Encoding]::ASCII.GetString($buf)
        } finally { $fs.Dispose() }
    } catch { return $null }
}

$rows = New-Object System.Collections.Generic.List[object]
# Bug 3: SilentlyContinue hid unreadable folders entirely. Capture and report.
$scanErrors = @()
$files = Get-ChildItem -LiteralPath $Path -Recurse -File -Force `
            -ErrorAction SilentlyContinue -ErrorVariable +scanErrors

Write-Host ("Found {0} files. Classifying..." -f $files.Count) -ForegroundColor Cyan

$i = 0
foreach ($f in $files) {
    $i++
    if ($i % 250 -eq 0) { Write-Host "  $i / $($files.Count)" }

    $cloudOnly = (($f.Attributes.value__ -band $RECALL) -ne 0)
    $row = [ordered]@{
        Path        = $f.FullName
        Name        = $f.Name
        Ext         = $f.Extension.ToLower()
        SizeBytes   = $f.Length
        Modified    = $f.LastWriteTimeUtc.ToString('yyyy-MM-dd')
        WasCloudOnly = $cloudOnly
        Read         = $false
        Type        = 'OTHER'
        Callsign    = ''
        Contest     = ''
        Year        = ''
        QsoCount    = ''
        Note        = ''
    }

    if ($cloudOnly -and -not $HydrateCloudFiles) {
        $row.Note = 'online-only placeholder; not read (use -HydrateCloudFiles)'
        $rows.Add([pscustomobject]$row); continue
    }

    # Documentation and source files can quote log or cty content verbatim and
    # would otherwise classify as data. Never content-sniff these.
    if ($row.Ext -in '.md','.rst','.py','.ps1','.json','.yaml','.yml') {
        $row.Note = 'documentation/source - not classified'
        $rows.Add([pscustomobject]$row); continue
    }

    # Cheap extension-only classifications first - avoid reading big binaries.
    if ($row.Ext -eq '.s3db') {
        $row.Type = 'N1MM_DB'
        $row.Read = $true
        $row.Note = 'N1MM contest database - contains logged QSOs'
        $rows.Add([pscustomobject]$row); continue
    }

    if ($row.Ext -in $BinaryExt) {
        $row.Note = 'binary extension - not content-sniffed'
        $rows.Add([pscustomobject]$row); continue
    }

    $head = Get-Head -File $f.FullName
    if ($null -eq $head) {
        $row.Note = 'binary or unreadable - not content-sniffed'
        $rows.Add([pscustomobject]$row); continue
    }
    # Bug 2: the attribute was sampled before hydration. Record that we actually
    # read the bytes, separately from whether it started as a placeholder.
    $row.Read = $true

    if ($head -match 'START-OF-LOG') {
        $row.Type = 'CABRILLO'
        if ($head -match '(?im)^CALLSIGN:\s*(\S+)')  { $row.Callsign = $Matches[1].ToUpper() }
        if ($head -match '(?im)^CONTEST:\s*(\S+)')   { $row.Contest  = $Matches[1].ToUpper() }
        if ($head -match '(?im)^QSO:\s+\S+\s+\S+\s+(\d{4})-') { $row.Year = $Matches[1] }
        # Full read only for the QSO count - Cabrillo logs are small.
        try {
            $row.QsoCount = (Select-String -LiteralPath $f.FullName -Pattern '^QSO:' -AllMatches).Count
        } catch { }
    }
    elseif ($row.Ext -eq '.rpt' -or
            $head -match '(?i)log\s*check' -or
            ($head -match '(?i)\bUBN\b'      -and $head -match '(?im)^\s*Call:') -or
            ($head -match '(?i)\bnot in log\b' -and $head -match '(?i)\bQSO:')) {
        $row.Type = 'LCR_UBN'
        if ($head -match '(?im)Call:\s*(\S+)') { $row.Callsign = $Matches[1].ToUpper() }
        if ($head -match '(?i)(\d{4})\s+CQ\s*(WW|WORLD)') { $row.Year = $Matches[1] }
        $row.Note = 'HIGHEST VALUE - names every denied QSO and why'
    }
    elseif ($head -match '(?i)<EOH>|<CALL:\d+>') {
        $row.Type = 'ADIF'
    }
    elseif ($head -match 'VER\d{8}' -or ($head -match '(?m)^\s*\w[\w .&''\-/]*:\s+\d{1,2}:\s+\d{1,2}:\s+[A-Z]{2}:')) {
        $row.Type = 'CTY'
        if ($head -match '(VER\d{8})') { $row.Note = $Matches[1] }
    }
    elseif ($row.Name -match '(?i)master.*\.scp$' -or $row.Ext -eq '.scp') {
        $row.Type = 'SCP'
        try { $row.Note = "$((Get-Content -LiteralPath $f.FullName | Measure-Object -Line).Lines) lines" } catch { }
    }
    elseif ($head -match '(?im)^!!Order!!') {
        $row.Type = 'CALLHISTORY'
        $row.Note = 'N1MM call history - check the Sect column carries the CQ zone'
    }

    $rows.Add([pscustomobject]$row)
}

$rows | Export-Csv -LiteralPath $OutCsv -NoTypeInformation -Encoding UTF8
Write-Host "`nManifest -> $OutCsv" -ForegroundColor Green

Write-Host "`n=== SUMMARY ===" -ForegroundColor Yellow
$rows | Group-Object Type | Sort-Object Count -Descending |
    Format-Table @{n='Type';e={$_.Name}}, Count -AutoSize

$wasCloud = ($rows | Where-Object WasCloudOnly).Count
$notRead  = ($rows | Where-Object { -not $_.Read }).Count
Write-Host ("{0} file(s) started as OneDrive placeholders; {1} were not read." -f $wasCloud, $notRead) -ForegroundColor Yellow
if ($notRead -gt 0 -and -not $HydrateCloudFiles) {
    Write-Host "Re-run with -HydrateCloudFiles to download and classify them." -ForegroundColor Yellow
}
if ($scanErrors.Count -gt 0) {
    Write-Host "`nWARNING: $($scanErrors.Count) folder(s) could not be entered:" -ForegroundColor Red
    $scanErrors | Select-Object -First 10 | ForEach-Object { Write-Host "  $($_.TargetObject)" }
} else {
    Write-Host "All folders were readable (0 traversal errors)." -ForegroundColor DarkGray
}
Write-Host "`nNOTE: $OutCsv lists every filename in the tree, which may include" -ForegroundColor DarkYellow
Write-Host "personal documents. It defaults outside any repo. Do not commit it." -ForegroundColor DarkYellow

Write-Host "`n=== CONTEST LOGS FOUND ===" -ForegroundColor Yellow
$rows | Where-Object { $_.Type -eq 'CABRILLO' } |
    Sort-Object Year, Callsign |
    Format-Table Callsign, Contest, Year, QsoCount, SizeBytes, Name -AutoSize

Write-Host "`n=== LOG CHECKING REPORTS (UBN) - HIGHEST VALUE ===" -ForegroundColor Yellow
$lcr = $rows | Where-Object { $_.Type -eq 'LCR_UBN' }
if ($lcr) { $lcr | Format-Table Callsign, Year, SizeBytes, Name -AutoSize }
else { Write-Host "  none found in this tree - check Gmail instead" -ForegroundColor DarkYellow }

Write-Host "`n=== N1MM DATABASES ===" -ForegroundColor Yellow
$rows | Where-Object { $_.Type -eq 'N1MM_DB' } | Format-Table Name, SizeBytes, Modified -AutoSize

if ($StageTo) {
    Write-Host "`nStaging to $StageTo ..." -ForegroundColor Cyan
    $map = @{
        CABRILLO    = 'logs'
        LCR_UBN     = 'lcr'
        ADIF        = 'adif'
        N1MM_DB     = 'n1mm'
        CTY         = 'cty'
        SCP         = 'scp'
        CALLHISTORY = 'callhistory'
    }
    foreach ($r in $rows) {
        if (-not $map.ContainsKey($r.Type)) { continue }
        $dest = Join-Path $StageTo $map[$r.Type]
        New-Item -ItemType Directory -Force -Path $dest | Out-Null
        # Keep names unique: some folders hold several logs with the same name.
        $target = Join-Path $dest $r.Name
        if (Test-Path -LiteralPath $target) {
            $stamp = [IO.Path]::GetFileNameWithoutExtension($r.Name) + '_' +
                     (Get-Random -Maximum 99999) + [IO.Path]::GetExtension($r.Name)
            $target = Join-Path $dest $stamp
        }
        Copy-Item -LiteralPath $r.Path -Destination $target -Force
    }
    Write-Host "Staged. Copy these into the BFA repo under data/ and commit BYTE-UNMODIFIED." -ForegroundColor Green
}
