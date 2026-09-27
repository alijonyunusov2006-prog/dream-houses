#Requires -Version 5.1
<#
.SYNOPSIS
    Установка Jarvis (OpenJarvis) на Windows одним запуском.

.DESCRIPTION
    Обёртка над официальным установщиком OpenJarvis для Windows
    (deploy/windows/install.ps1). Делает то, чего официальный установщик
    не делает сам, чтобы установка прошла с первого раза на «чистом» ПК:

      1. Проверяет Windows, память и место на диске.
      2. Ставит Python 3.13, Git, Visual Studio Build Tools (C++) и Rust —
         они нужны, чтобы собрать нативный модуль Jarvis (openjarvis_rust).
      3. Обходит ловушку «python3 из Microsoft Store» (заглушка в WindowsApps,
         из-за которой официальный установщик падает на проверке версии).
      4. Запускает официальный установщик: uv, исходники в
         %LOCALAPPDATA%\OpenJarvis\src, зависимости, Ollama, стартовая модель.
      5. Ставит десктопное приложение OpenJarvis (последний релиз с GitHub).
      6. Создаёт ярлык «Jarvis» на рабочем столе и добавляет в автозагрузку.
      7. Запускает Jarvis.

    Повторный запуск безопасен: готовые шаги пропускаются.

.PARAMETER NoAutostart
    Не добавлять Jarvis в автозагрузку Windows.

.PARAMETER NoDesktopApp
    Не ставить десктопное приложение (только консольный jarvis).

.PARAMETER Force
    Передать -Force официальному установщику (переустановить все шаги).

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File .\install-jarvis.ps1
#>

[CmdletBinding()]
param(
    [switch] $NoAutostart,
    [switch] $NoDesktopApp,
    [switch] $Force
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # прогресс-бар замедляет загрузки в PS 5.1 в 30 раз
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
# GitHub принимает только TLS 1.2+, а PowerShell 5.1 на старых Windows 10 по умолчанию его не включает.
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch { }

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

$InstallRoot = if ($env:OPENJARVIS_HOME) { $env:OPENJARVIS_HOME } else { Join-Path $env:LOCALAPPDATA 'OpenJarvis' }
$SrcDir      = Join-Path $InstallRoot 'src'
$BinDir      = Join-Path $InstallRoot 'bin'
$ShimDir     = Join-Path $InstallRoot 'pyshim'
$LogDir      = Join-Path $InstallRoot 'logs'
$LogFile     = Join-Path $LogDir ("install-{0:yyyyMMdd-HHmmss}.log" -f (Get-Date))

# Официальный установщик. Первый URL — файл прямо из репозитория, второй —
# копия на GitHub Pages проекта (иногда недоступна из некоторых сетей).
$OfficialInstallerUrls = @(
    'https://raw.githubusercontent.com/open-jarvis/OpenJarvis/main/deploy/windows/install.ps1',
    'https://open-jarvis.github.io/OpenJarvis/install.ps1'
)

# Манифест последнего десктопного релиза (его же читает автообновление приложения).
$DesktopLatestJson = 'https://github.com/open-jarvis/OpenJarvis/releases/download/desktop-latest/latest.json'

# Команда, которую десктопное приложение выполняет при первом запуске.
# Выполняем заранее, чтобы первый запуск не висел на «Installing dependencies».
$DesktopSyncArgs = @('sync', '--extra', 'desktop', '--extra', 'inference-cloud', '--extra', 'inference-google', '--group', 'desktop-native')

# Rust-воркспейс OpenJarvis закреплён на 1.88 (rust/rust-toolchain.toml).
$RustChannel = '1.88'

$MinFreeGB  = 6     # меньше — установка не запустится
$WantFreeGB = 12    # меньше — предупреждение (Build Tools + модели занимают много)

# ---------------------------------------------------------------------------
# Вывод
# ---------------------------------------------------------------------------

function Write-Step ($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok   ($msg) { Write-Host "    [ok]   $msg" -ForegroundColor Green }
function Write-Info ($msg) { Write-Host "    $msg" }
function Write-Warn2($msg) { Write-Host "    [!]    $msg" -ForegroundColor Yellow }
function Write-Fail ($msg) { throw [System.InvalidOperationException]::new([string] $msg) }

# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

# Запуск внешней программы (winget, uv, rustup...). В PowerShell 5.1 при
# $ErrorActionPreference = 'Stop' обычный вывод программы в stderr может
# превратиться в исключение и оборвать установку. Здесь это отключено.
# Возвращает код выхода программы.
function Invoke-Native ([scriptblock] $Block) {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Block | Out-Host
        return $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
    }
}

# Подтянуть актуальный PATH из реестра (Machine + User) и добавить каталоги,
# которые ставятся в текущем запуске, но в реестр попадут только позже.
function Refresh-Path {
    $machine = [System.Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user    = [System.Environment]::GetEnvironmentVariable('Path', 'User')
    $combined = [System.Environment]::ExpandEnvironmentVariables("$machine;$user")
    $extra = @(
        $ShimDir,
        (Join-Path $env:USERPROFILE '.cargo\bin'),
        (Join-Path $env:USERPROFILE '.local\bin'),
        $BinDir
    ) | Where-Object { $_ -and (Test-Path $_) }
    $env:Path = ((@($extra) + @($combined)) -join ';')
}

function Test-Cmd ($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Get-FreeGB ($path) {
    $root = [System.IO.Path]::GetPathRoot($path)
    $drive = Get-PSDrive -Name $root.Substring(0, 1) -ErrorAction SilentlyContinue
    if (-not $drive) { return 0 }
    return [math]::Round($drive.Free / 1GB, 1)
}

function Get-RamGB {
    try {
        $cs = Get-CimInstance Win32_ComputerSystem
        return [math]::Round($cs.TotalPhysicalMemory / 1GB, 1)
    } catch { return 0 }
}

# winget install с принятыми соглашениями. Код выхода только для журнала:
# вызывающий код всегда проверяет результат повторным поиском программы.
function Install-Winget {
    param([string] $Id, [string] $Override)
    if (-not (Test-Cmd winget)) { Write-Warn2 "winget недоступен, пропускаю установку $Id"; return }
    $wingetArgs = @('install', '--id', $Id, '--exact', '--silent',
                    '--accept-source-agreements', '--accept-package-agreements')
    if ($Override) { $wingetArgs += @('--override', $Override) }
    Write-Info "winget install $Id ..."
    $code = Invoke-Native { & winget @wingetArgs }
    # 0 — установлено; -1978335189 (0x8A15002B) — уже стоит, обновлять нечего.
    if ($code -ne 0 -and $code -ne -1978335189) { Write-Warn2 "winget вернул код $code" }
    Refresh-Path
}

function Download-File {
    param([string] $Url, [string] $OutFile)
    $dir = Split-Path $OutFile -Parent
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing
}

# Настоящий Python 3.10–3.13. Заглушки Microsoft Store (…\WindowsApps\python*.exe)
# пропускаем: они не Python, а ссылка на магазин.
function Find-RealPython {
    $candidates = @()
    foreach ($name in @('python', 'python3')) {
        foreach ($cmd in @(Get-Command $name -All -ErrorAction SilentlyContinue)) {
            if ($cmd.Source) { $candidates += $cmd.Source }
        }
    }
    foreach ($v in @('313', '312', '311', '310')) {
        $candidates += (Join-Path $env:LOCALAPPDATA "Programs\Python\Python$v\python.exe")
        $candidates += "C:\Python$v\python.exe"
        $candidates += (Join-Path $env:ProgramFiles "Python$v\python.exe")
    }
    if (Test-Cmd py) {
        $p = $null
        [void](Invoke-Native { $script:pyExe = & py -3 -c "import sys; print(sys.executable)" 2>$null })
        if ($script:pyExe) { $candidates += "$($script:pyExe)".Trim() }
    }
    foreach ($c in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
        if ($c -like '*\WindowsApps\*') { continue }
        if (-not (Test-Path $c)) { continue }
        $script:pyVer = $null
        [void](Invoke-Native { $script:pyVer = & $c --version 2>&1 })
        $m = [regex]::Match("$($script:pyVer)", '(\d+)\.(\d+)\.(\d+)')
        if (-not $m.Success) { continue }
        $major = [int]$m.Groups[1].Value; $minor = [int]$m.Groups[2].Value
        if ($major -eq 3 -and $minor -ge 10 -and $minor -le 13) {
            return [pscustomobject]@{ Path = $c; Version = "$major.$minor.$($m.Groups[3].Value)" }
        }
    }
    return $null
}

function Find-MsvcTools {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (-not (Test-Path $vswhere)) { return $null }
    $script:vsPath = $null
    [void](Invoke-Native { $script:vsPath = & $vswhere -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath -latest 2>$null })
    if ($script:vsPath) { return "$($script:vsPath)".Trim() }
    return $null
}

function Find-Cargo {
    $c = Get-Command cargo -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    $fallback = Join-Path $env:USERPROFILE '.cargo\bin\cargo.exe'
    if (Test-Path $fallback) { return $fallback }
    return $null
}

function Find-DesktopExe {
    $candidates = @(
        (Join-Path $InstallRoot 'OpenJarvis.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\OpenJarvis\OpenJarvis.exe'),
        (Join-Path $env:ProgramFiles 'OpenJarvis\OpenJarvis.exe')
    )
    foreach ($hive in @('HKCU', 'HKLM')) {
        foreach ($name in @('OpenJarvis', 'com.openjarvis.desktop')) {
            try {
                $loc = (Get-ItemProperty -Path "${hive}:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$name" -ErrorAction Stop).InstallLocation
                if ($loc) { $candidates += (Join-Path $loc 'OpenJarvis.exe') }
            } catch { }
        }
    }
    foreach ($c in $candidates) { if ($c -and (Test-Path $c)) { return $c } }
    return $null
}

function New-Shortcut {
    param([string] $Path, [string] $Target, [string] $Arguments, [string] $Description)
    $shell = New-Object -ComObject WScript.Shell
    $lnk = $shell.CreateShortcut($Path)
    $lnk.TargetPath = $Target
    if ($Arguments) { $lnk.Arguments = $Arguments }
    $lnk.WorkingDirectory = Split-Path $Target -Parent
    $lnk.IconLocation = "$Target,0"
    if ($Description) { $lnk.Description = $Description }
    $lnk.Save()
}

# ---------------------------------------------------------------------------
# Основной сценарий
# ---------------------------------------------------------------------------

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
try { Start-Transcript -Path $LogFile -Append | Out-Null } catch { }

$desktopExe = $null
$ollamaOk   = $false

try {
    Write-Host ""
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host "    Установка Jarvis (OpenJarvis)" -ForegroundColor Cyan
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Info "Папка установки: $InstallRoot"
    Write-Info "Журнал:          $LogFile"
    Write-Host ""
    Write-Warn2 "Установка занимает 30–60 минут и скачивает 5–7 ГБ."
    Write-Warn2 "Несколько раз появится окно Windows «Разрешить внесение изменений?» — нажимайте «Да»."
    Write-Warn2 "Не закрывайте это окно до надписи «Готово»."

    # ---- 1. Система ------------------------------------------------------
    Write-Step "Проверяю систему"

    if ($PSVersionTable.Platform -and $PSVersionTable.Platform -ne 'Win32NT') {
        Write-Fail "Этот установщик только для Windows."
    }
    $build = [System.Environment]::OSVersion.Version.Build
    if ($build -lt 17763) { Write-Fail "Нужна Windows 10 1809 (сборка 17763) или новее. У вас сборка $build." }
    if (-not [System.Environment]::Is64BitOperatingSystem) { Write-Fail "Нужна 64-битная Windows." }
    Write-Ok "Windows, сборка $build"

    $ram = Get-RamGB
    if ($ram -gt 0) {
        if ($ram -lt 7.5)       { Write-Warn2 "Оперативной памяти $ram ГБ. Jarvis запустится, но модели будут маленькие и медленные. Рекомендуется 16 ГБ." }
        elseif ($ram -lt 15.5)  { Write-Ok "Память $ram ГБ (хватит для моделей 2–4B; для 9B нужно 16 ГБ)" }
        else                    { Write-Ok "Память $ram ГБ" }
    }

    if (-not (Test-Path $InstallRoot)) { New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null }
    $free = Get-FreeGB $InstallRoot
    if ($free -gt 0) {
        if ($free -lt $MinFreeGB) { Write-Fail "На диске с папкой $InstallRoot свободно $free ГБ. Нужно минимум $MinFreeGB ГБ (лучше $WantFreeGB+)." }
        if ($free -lt $WantFreeGB) { Write-Warn2 "Свободно $free ГБ. Хватит впритык; рекомендуется $WantFreeGB ГБ и больше." } else { Write-Ok "Свободно $free ГБ" }
    }

    if (-not (Test-Cmd winget)) {
        Write-Fail @"
Не найден winget (менеджер пакетов Windows). Он нужен, чтобы поставить Python, Git и инструменты сборки.
Откройте Microsoft Store, установите/обновите «Установщик приложения» (App Installer):
    https://apps.microsoft.com/detail/9NBLGGH4NNS1
Затем запустите этот установщик ещё раз.
"@
    }
    Write-Ok "winget найден"

    try {
        Invoke-WebRequest -Uri 'https://github.com' -UseBasicParsing -Method Head -TimeoutSec 20 | Out-Null
        Write-Ok "Интернет есть (github.com доступен)"
    } catch {
        Write-Fail "Нет доступа к github.com: $($_.Exception.Message). Проверьте интернет и запустите снова."
    }

    Refresh-Path

    # ---- 2. Python -------------------------------------------------------
    Write-Step "Python 3.10–3.13"
    $python = Find-RealPython
    if (-not $python) {
        Write-Info "Python не найден, ставлю Python 3.13 (~30 МБ)..."
        Install-Winget -Id 'Python.Python.3.13'
        $python = Find-RealPython
        if (-not $python) {
            Write-Fail "Не удалось поставить Python. Установите вручную с https://www.python.org/downloads/ (галочка «Add python.exe to PATH») и запустите снова."
        }
    }
    Write-Ok "Python $($python.Version) — $($python.Path)"

    # Шим: в Windows команда python3 — заглушка Microsoft Store. Официальный
    # установщик проверяет именно python3 и падает на ней. Подменяем.
    if (-not (Test-Path $ShimDir)) { New-Item -ItemType Directory -Path $ShimDir -Force | Out-Null }
    foreach ($name in @('python3.cmd', 'python.cmd')) {
        Set-Content -Path (Join-Path $ShimDir $name) -Value "@`"$($python.Path)`" %*" -Encoding ASCII
    }
    Refresh-Path

    # ---- 3. Git ----------------------------------------------------------
    Write-Step "Git"
    if (-not (Test-Cmd git)) {
        Write-Info "Git не найден, ставлю (~60 МБ)..."
        Install-Winget -Id 'Git.Git'
        if (-not (Test-Cmd git)) { Write-Fail "Не удалось поставить Git. Установите вручную с https://git-scm.com/download/win и запустите снова." }
    }
    Write-Ok "git — $((Get-Command git).Source)"

    # ---- 4. Visual Studio Build Tools (C++) -------------------------------
    Write-Step "Инструменты сборки C++ (Visual Studio Build Tools)"
    Write-Info "Нужны один раз: без них не собирается нативный модуль Jarvis (openjarvis_rust)."
    $msvc = Find-MsvcTools
    if (-not $msvc) {
        Write-Info "Ставлю Build Tools 2022 с компонентом C++ (~3–4 ГБ, 10–20 минут). Появится запрос прав администратора."
        $override = '--quiet --wait --norestart --nocache --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended'
        Install-Winget -Id 'Microsoft.VisualStudio.2022.BuildTools' -Override $override
        $msvc = Find-MsvcTools
        if (-not $msvc) {
            Write-Fail @"
Build Tools не установились или установились без компонента C++.
Поставьте вручную: https://aka.ms/vs/17/release/vs_BuildTools.exe
В установщике отметьте «Разработка классических приложений на C++» (Desktop development with C++), затем запустите этот установщик снова.
"@
        }
    }
    Write-Ok "MSVC — $msvc"

    # ---- 5. Rust ---------------------------------------------------------
    Write-Step "Rust ($RustChannel)"
    $cargo = Find-Cargo
    if (-not $cargo) {
        Write-Info "Rust не найден, ставлю rustup (~300 МБ)..."
        Install-Winget -Id 'Rustlang.Rustup'
        $cargo = Find-Cargo
        if (-not $cargo) { Write-Fail "Не удалось поставить Rust. Установите вручную с https://rustup.rs и запустите снова." }
    }
    Write-Ok "cargo — $cargo"
    $rustup = Join-Path (Split-Path $cargo -Parent) 'rustup.exe'
    if (Test-Path $rustup) {
        Write-Info "Проверяю toolchain $RustChannel (скачается при первом запуске)..."
        $code = Invoke-Native { & $rustup toolchain install $RustChannel --profile minimal -c rustfmt -c clippy }
        if ($code -ne 0) { Write-Warn2 "rustup вернул код $code — продолжаю, сборка попробует сама." }
    }

    # ---- 6. Официальный установщик OpenJarvis ---------------------------
    Write-Step "Официальный установщик OpenJarvis"
    Write-Info "Исходники, зависимости Python, сборка нативного модуля (10–30 минут), Ollama, стартовая модель (~1.5 ГБ)."
    $official = Join-Path $InstallRoot 'install-official.ps1'
    $downloaded = $false
    foreach ($url in $OfficialInstallerUrls) {
        try {
            Download-File -Url $url -OutFile $official
            $downloaded = $true
            Write-Ok "Скачан: $url"
            break
        } catch {
            Write-Warn2 "Не скачался $url — $($_.Exception.Message)"
        }
    }
    if (-not $downloaded) { Write-Fail "Не удалось скачать официальный установщик ни по одному адресу." }

    # Автозапуск делаем сами (через десктопное приложение), поэтому -SkipService.
    # Дочерний процесс наследует наш PATH с шимом python3, cargo и uv.
    $officialArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $official, '-SkipService')
    if ($Force) { $officialArgs += '-Force' }
    $code = Invoke-Native { & powershell @officialArgs }
    if ($code -ne 0) {
        Write-Fail "Официальный установщик завершился с ошибкой (код $code). Подробности выше и в журнале: $LogFile"
    }
    Refresh-Path
    if (-not (Test-Path (Join-Path $SrcDir 'pyproject.toml'))) {
        Write-Fail "Исходники OpenJarvis не найдены в $SrcDir после установки."
    }
    Write-Ok "OpenJarvis установлен в $SrcDir"
    $ollamaOk = Test-Cmd ollama

    # ---- 7. Полный набор зависимостей десктопного приложения -------------
    Write-Step "Зависимости десктопного приложения"
    $uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
    if (-not $uv) {
        $uvFallback = Join-Path $env:USERPROFILE '.local\bin\uv.exe'
        if (Test-Path $uvFallback) { $uv = $uvFallback }
    }
    if (-not $uv) { Write-Fail "uv не найден после официальной установки." }
    Push-Location $SrcDir
    try {
        $code = Invoke-Native { & $uv @DesktopSyncArgs }
        if ($code -ne 0) {
            Write-Warn2 "uv sync вернул код $code. Приложение повторит установку при первом запуске."
        } else {
            Write-Ok "Зависимости готовы"
        }
    } finally { Pop-Location }

    # Приложение ищет исходники по этой переменной первым делом — задаём явно,
    # чтобы не зависеть от того, куда именно встал .exe.
    [System.Environment]::SetEnvironmentVariable('OPENJARVIS_ROOT', $SrcDir, 'User')
    $env:OPENJARVIS_ROOT = $SrcDir

    # ---- 8. Десктопное приложение ----------------------------------------
    if (-not $NoDesktopApp) {
        Write-Step "Десктопное приложение OpenJarvis"
        $desktopExe = Find-DesktopExe
        if ($desktopExe -and -not $Force) {
            Write-Ok "Уже установлено — $desktopExe"
        } else {
            $setupUrl = $null
            $msiUrl = $null
            try {
                $tmpJson = Join-Path $env:TEMP 'openjarvis-latest.json'
                Download-File -Url $DesktopLatestJson -OutFile $tmpJson
                $manifest = Get-Content $tmpJson -Raw | ConvertFrom-Json
                $msiUrl = $manifest.platforms.'windows-x86_64'.url
                Write-Info "Версия приложения: $($manifest.version)"
                if ($msiUrl) {
                    # В релизе рядом с .msi лежит NSIS-установщик *_x64-setup.exe:
                    # ставится в %LOCALAPPDATA%\OpenJarvis без прав администратора.
                    $setupUrl = $msiUrl -replace '_x64_en-US\.msi$', '_x64-setup.exe'
                }
            } catch {
                Write-Warn2 "Не удалось прочитать манифест релиза: $($_.Exception.Message)"
            }

            $installed = $false
            if ($setupUrl) {
                $setupFile = Join-Path $env:TEMP 'OpenJarvis-setup.exe'
                try {
                    Write-Info "Скачиваю $setupUrl ..."
                    Download-File -Url $setupUrl -OutFile $setupFile
                    Write-Info "Устанавливаю (тихо)..."
                    $p = Start-Process -FilePath $setupFile -ArgumentList '/S' -Wait -PassThru
                    if ($p.ExitCode -eq 0) { $installed = $true } else { Write-Warn2 "Установщик вернул код $($p.ExitCode)" }
                } catch {
                    Write-Warn2 "NSIS-установщик не сработал: $($_.Exception.Message)"
                } finally {
                    Remove-Item $setupFile -ErrorAction SilentlyContinue
                }
            }
            if (-not $installed -and $msiUrl) {
                $msiFile = Join-Path $env:TEMP 'OpenJarvis-setup.msi'
                try {
                    Write-Info "Пробую MSI: $msiUrl ..."
                    Download-File -Url $msiUrl -OutFile $msiFile
                    $p = Start-Process -FilePath 'msiexec.exe' -ArgumentList "/i `"$msiFile`" /passive /norestart" -Wait -PassThru
                    if ($p.ExitCode -eq 0 -or $p.ExitCode -eq 3010) { $installed = $true } else { Write-Warn2 "msiexec вернул код $($p.ExitCode)" }
                } catch {
                    Write-Warn2 "MSI-установщик не сработал: $($_.Exception.Message)"
                } finally {
                    Remove-Item $msiFile -ErrorAction SilentlyContinue
                }
            }
            $desktopExe = Find-DesktopExe
            if ($desktopExe) {
                Write-Ok "Приложение установлено — $desktopExe"
            } else {
                Write-Warn2 "Десктопное приложение не установилось. Консольный jarvis работает; приложение можно скачать вручную:"
                Write-Warn2 "https://github.com/open-jarvis/OpenJarvis/releases"
            }
        }
    }

    # ---- 9. Ярлыки и автозагрузка ----------------------------------------
    Write-Step "Ярлыки и автозагрузка"
    $desktopDir = [System.Environment]::GetFolderPath('Desktop')
    if ($desktopExe) {
        New-Shortcut -Path (Join-Path $desktopDir 'Jarvis.lnk') -Target $desktopExe -Description 'Jarvis — ИИ-ассистент (OpenJarvis)'
        Write-Ok "Ярлык «Jarvis» на рабочем столе"

        if (-not $NoAutostart) {
            # Тот же ключ, что использует встроенный переключатель автозапуска
            # приложения, поэтому его настройка «Launch at login» останется согласованной.
            $runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
            New-ItemProperty -Path $runKey -Name 'OpenJarvis' -Value "`"$desktopExe`" --hidden" -PropertyType String -Force | Out-Null
            Write-Ok "Автозагрузка: Jarvis стартует при входе в Windows (свернут в трей)"
        }
    } else {
        # Нет приложения — ярлык на консольный чат.
        $jarvisCmd = Join-Path $BinDir 'jarvis.cmd'
        if (Test-Path $jarvisCmd) {
            New-Shortcut -Path (Join-Path $desktopDir 'Jarvis (консоль).lnk') -Target "$env:SystemRoot\System32\cmd.exe" -Arguments "/k `"`"$jarvisCmd`"`"" -Description 'Jarvis в консоли'
            Write-Ok "Ярлык «Jarvis (консоль)» на рабочем столе"
        }
    }

    # ---- 10. Запуск ------------------------------------------------------
    Write-Step "Запускаю Jarvis"
    if ($desktopExe) {
        Start-Process -FilePath $desktopExe -WorkingDirectory (Split-Path $desktopExe -Parent)
        Write-Ok "Приложение запущено. При первом запуске оно спросит, какой движок использовать — выбирайте Ollama (локально)."
    } else {
        Write-Info "Откройте новое окно PowerShell и введите:  jarvis"
    }

    Write-Host ""
    Write-Host "  ============================================" -ForegroundColor Green
    Write-Host "    Готово. Jarvis установлен." -ForegroundColor Green
    Write-Host "  ============================================" -ForegroundColor Green
    Write-Host ""
    Write-Info "Ярлык:        Рабочий стол → Jarvis"
    Write-Info "Консоль:      новое окно PowerShell → jarvis   (jarvis doctor — диагностика)"
    Write-Info "Исходники:    $SrcDir"
    Write-Info "Журнал:       $LogFile"
    if (-not $ollamaOk) { Write-Warn2 "Ollama не найден в PATH — если чат не отвечает, откройте новое окно PowerShell и выполните: jarvis doctor" }
    Write-Host ""
}
catch {
    Write-Host ""
    Write-Host "  ОШИБКА: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "  Журнал: $LogFile" -ForegroundColor Red
    Write-Host "  Повторный запуск безопасен — готовые шаги будут пропущены." -ForegroundColor Yellow
    Write-Host ""
    try { Stop-Transcript | Out-Null } catch { }
    exit 1
}
finally {
    try { Stop-Transcript | Out-Null } catch { }
}
