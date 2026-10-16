#Requires -Version 5.1
<#
.SYNOPSIS
    Аудит диска для JARVIS: что занимает место. Ничего не удаляет и не перемещает.

.DESCRIPTION
    Собирает: свободное место по дискам, размеры папок первых двух уровней под каждым
    корнем, самые большие файлы, размеры известных кэшей/temp, сводку по расширениям.
    Пишет отчёт Markdown + JSON в -OutDir (по умолчанию data/reports рядом с репозиторием).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File core/scripts/Disk-Audit.ps1 -Roots C:\ -MinFileMB 500 -TopN 60
#>

[CmdletBinding()]
param(
    [string[]] $Roots = @(),
    [int] $MinFileMB = 500,
    [int] $TopN = 50,
    [int] $Depth = 2,
    [string] $OutDir = ""
)

$ErrorActionPreference = 'SilentlyContinue'
$ProgressPreference = 'SilentlyContinue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$IsWin = ($env:OS -eq 'Windows_NT')
if (-not $Roots -or $Roots.Count -eq 0) { $Roots = if ($IsWin) { @('C:\') } else { @($HOME) } }
if (-not $OutDir) { $OutDir = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) 'data/reports' }
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

$stamp = Get-Date -Format 'yyyyMMdd-HHmm'
$mdPath = Join-Path $OutDir "disk-audit-$stamp.md"
$jsonPath = Join-Path $OutDir "disk-audit-$stamp.json"

function Format-GB ([double] $bytes) {
    if ($bytes -ge 1GB) { return ('{0:N1} ГБ' -f ($bytes / 1GB)) }
    return ('{0:N0} МБ' -f ($bytes / 1MB))
}

# Размер папки: сумма файлов рекурсивно, без переходов по junction/symlink.
function Get-DirSize ([string] $path) {
    $sum = 0L
    $files = Get-ChildItem -LiteralPath $path -File -Recurse -Force -Attributes !ReparsePoint -ErrorAction SilentlyContinue
    foreach ($f in $files) { $sum += $f.Length }
    return $sum
}

$report = [ordered]@{
    generated = (Get-Date).ToString('s')
    roots     = $Roots
    drives    = @()
    folders   = @()
    big_files = @()
    caches    = @()
    by_ext    = @()
}

# --- диски ---------------------------------------------------------------
foreach ($d in (Get-PSDrive -PSProvider FileSystem)) {
    if ($null -eq $d.Used -and $null -eq $d.Free) { continue }
    $report.drives += [pscustomobject]@{ name = $d.Name; used_gb = [math]::Round(($d.Used / 1GB), 1); free_gb = [math]::Round(($d.Free / 1GB), 1) }
}

# --- папки первых уровней -------------------------------------------------
$skipNames = @('$Recycle.Bin', 'System Volume Information', 'Windows', 'WinSxS')
foreach ($root in $Roots) {
    if (-not (Test-Path -LiteralPath $root)) { continue }
    $level1 = Get-ChildItem -LiteralPath $root -Directory -Force -Attributes !ReparsePoint
    foreach ($d1 in $level1) {
        if ($skipNames -contains $d1.Name) { continue }
        $size1 = Get-DirSize $d1.FullName
        $report.folders += [pscustomobject]@{ path = $d1.FullName; depth = 1; bytes = $size1 }
        if ($Depth -ge 2) {
            foreach ($d2 in (Get-ChildItem -LiteralPath $d1.FullName -Directory -Force -Attributes !ReparsePoint)) {
                $size2 = Get-DirSize $d2.FullName
                if ($size2 -gt 1GB) { $report.folders += [pscustomobject]@{ path = $d2.FullName; depth = 2; bytes = $size2 } }
            }
        }
    }
}
$report.folders = @($report.folders | Sort-Object -Property bytes -Descending)

# --- большие файлы + расширения ------------------------------------------
$minBytes = [long]$MinFileMB * 1MB
$extTotals = @{}
$big = New-Object System.Collections.Generic.List[object]
foreach ($root in $Roots) {
    if (-not (Test-Path -LiteralPath $root)) { continue }
    Get-ChildItem -LiteralPath $root -File -Recurse -Force -Attributes !ReparsePoint -ErrorAction SilentlyContinue | ForEach-Object {
        $ext = if ($_.Extension) { $_.Extension.ToLower() } else { '(без расширения)' }
        if ($extTotals.ContainsKey($ext)) { $extTotals[$ext] += $_.Length } else { $extTotals[$ext] = [long]$_.Length }
        if ($_.Length -ge $minBytes) {
            $big.Add([pscustomobject]@{ path = $_.FullName; bytes = $_.Length; modified = $_.LastWriteTime.ToString('yyyy-MM-dd'); ext = $ext })
        }
    }
}
$report.big_files = @($big | Sort-Object -Property bytes -Descending | Select-Object -First $TopN)
$report.by_ext = @($extTotals.GetEnumerator() | Sort-Object -Property Value -Descending | Select-Object -First 25 |
    ForEach-Object { [pscustomobject]@{ ext = $_.Key; bytes = $_.Value } })

# --- известные кэши и temp ---------------------------------------------------
$cacheCandidates = @()
if ($IsWin) {
    $cacheCandidates = @(
        @{ name = 'TEMP пользователя';        path = $env:TEMP },
        @{ name = 'Windows\Temp';             path = 'C:\Windows\Temp' },
        @{ name = 'Windows.old';              path = 'C:\Windows.old' },
        @{ name = 'Загрузки';                 path = (Join-Path $env:USERPROFILE 'Downloads') },
        @{ name = 'pip cache';                path = (Join-Path $env:LOCALAPPDATA 'pip\Cache') },
        @{ name = 'uv cache';                 path = (Join-Path $env:LOCALAPPDATA 'uv\cache') },
        @{ name = 'npm cache';                path = (Join-Path $env:LOCALAPPDATA 'npm-cache') },
        @{ name = 'Ollama модели';            path = (Join-Path $env:USERPROFILE '.ollama\models') },
        @{ name = 'HuggingFace кэш';          path = (Join-Path $env:USERPROFILE '.cache\huggingface') },
        @{ name = '3ds Max autoback';         path = (Join-Path $env:LOCALAPPDATA 'Autodesk\3dsMax') },
        @{ name = 'Chrome кэш';               path = (Join-Path $env:LOCALAPPDATA 'Google\Chrome\User Data\Default\Cache') },
        @{ name = 'Edge кэш';                 path = (Join-Path $env:LOCALAPPDATA 'Microsoft\Edge\User Data\Default\Cache') },
        @{ name = 'Adobe Media Cache';        path = (Join-Path $env:APPDATA 'Adobe\Common\Media Cache Files') },
        @{ name = 'Корзина';                  path = 'C:\$Recycle.Bin' }
    )
} else {
    $cacheCandidates = @(
        @{ name = 'tmp';        path = '/tmp' },
        @{ name = 'pip cache';  path = (Join-Path $HOME '.cache/pip') },
        @{ name = 'uv cache';   path = (Join-Path $HOME '.cache/uv') }
    )
}
foreach ($c in $cacheCandidates) {
    if ($c.path -and (Test-Path -LiteralPath $c.path)) {
        $report.caches += [pscustomobject]@{ name = $c.name; path = $c.path; bytes = (Get-DirSize $c.path) }
    }
}
$report.caches = @($report.caches | Sort-Object -Property bytes -Descending)

# --- вывод -----------------------------------------------------------------
$md = New-Object System.Text.StringBuilder
[void]$md.AppendLine("# Аудит диска — $($report.generated)")
[void]$md.AppendLine("")
[void]$md.AppendLine("Корни: $($Roots -join ', ') · порог больших файлов: $MinFileMB МБ · ничего не удалено.")
[void]$md.AppendLine("")
[void]$md.AppendLine("## Диски")
foreach ($d in $report.drives) { [void]$md.AppendLine("- **$($d.name):** занято $($d.used_gb) ГБ, свободно **$($d.free_gb) ГБ**") }
[void]$md.AppendLine("")
[void]$md.AppendLine("## Папки по размеру (первые $TopN)")
foreach ($f in ($report.folders | Select-Object -First $TopN)) { [void]$md.AppendLine("- $(Format-GB $f.bytes) — ``$($f.path)``") }
[void]$md.AppendLine("")
[void]$md.AppendLine("## Самые большие файлы (≥ $MinFileMB МБ, первые $TopN)")
foreach ($f in $report.big_files) { [void]$md.AppendLine("- $(Format-GB $f.bytes) · $($f.modified) — ``$($f.path)``") }
[void]$md.AppendLine("")
[void]$md.AppendLine("## Кэши и temp")
foreach ($c in $report.caches) { [void]$md.AppendLine("- $(Format-GB $c.bytes) — $($c.name) (``$($c.path)``)") }
[void]$md.AppendLine("")
[void]$md.AppendLine("## По расширениям (топ-25)")
foreach ($e in $report.by_ext) { [void]$md.AppendLine("- $(Format-GB $e.bytes) — $($e.ext)") }

[System.IO.File]::WriteAllText($mdPath, $md.ToString(), (New-Object System.Text.UTF8Encoding($true)))
$report | ConvertTo-Json -Depth 6 | Set-Content -Path $jsonPath -Encoding UTF8

Write-Host "Отчёт: $mdPath"
Write-Host "JSON:  $jsonPath"
foreach ($d in $report.drives) { Write-Host "Диск $($d.name): свободно $($d.free_gb) ГБ" }
Write-Host "Папок учтено: $($report.folders.Count); больших файлов: $($report.big_files.Count); кэшей: $($report.caches.Count)"
