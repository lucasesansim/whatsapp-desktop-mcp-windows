[CmdletBinding()]
param(
    [string]$PythonPath,
    [string]$ReportPath,
    [switch]$PreflightOnly,
    [switch]$NonInteractive
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$buildDir = Join-Path $projectRoot 'work\read-only-test'
New-Item -Path $buildDir -ItemType Directory -Force | Out-Null
if (-not $PythonPath) { $PythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $PythonPath)) { throw 'Python del proyecto no encontrado. Instalar dependencias como indica README.' }
if (-not $ReportPath) { $ReportPath = Join-Path $buildDir 'result.json' }
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $compiler)) { throw 'Compilador .NET de Windows no encontrado.' }
$helperExe = Join-Path $buildDir 'WhatsAppThreadResumer.exe'
& $compiler '/nologo' '/target:winexe' ("/out:" + $helperExe) (Join-Path $PSScriptRoot 'WhatsAppThreadResumer.cs')
if ($LASTEXITCODE -ne 0) { throw 'No se pudo compilar el ayudante local.' }
if (-not ('ChatIATest.PackageDebugSession' -as [type])) {
    Add-Type -Path (Join-Path $PSScriptRoot 'PackageDebugSession.cs')
}
if ($PreflightOnly) { Write-Output 'Preflight OK. WhatsApp y sus opciones no fueron modificados.'; return }

Write-Host 'La prueba reinicia WhatsApp, lee una muestra y retira la conexion local. No envia mensajes.'
Write-Host 'No cerrar esta ventana hasta que termine la limpieza.'
if (-not $NonInteractive -and (Read-Host 'Escribi PROBAR para continuar') -cne 'PROBAR') { return }

$wa = @(Get-CimInstance Win32_Process -Filter "Name='WhatsApp.Root.exe'")
if ($wa.Count -ne 1) { throw 'Abri WhatsApp antes de ejecutar esta prueba.' }
$packageFullName = Split-Path -Leaf (Split-Path -Parent $wa[0].ExecutablePath)
$helperCommand = '"' + $helperExe + '"'
$debugSession = $null
$appRestarted = $false
$optionsRemoved = $false
$originalPort = $env:WHATSAPP_CDP_PORT
try {
    if (@(Get-NetTCPConnection -LocalPort 9224 -State Listen -ErrorAction SilentlyContinue).Count -gt 0) {
        throw 'El puerto de prueba esta ocupado. No se cambio WhatsApp.'
    }
    $debugSession = [ChatIATest.PackageDebugSession]::new($packageFullName,
        'WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-address=127.0.0.1 --remote-debugging-port=9224',
        $helperCommand)
    foreach ($process in $wa) { Stop-Process -Id $process.ProcessId -ErrorAction Stop }
    $appRestarted = $true
    Start-Sleep -Seconds 2
    $null = [ChatIATest.WhatsAppActivation]::Launch()
    $listeners = @()
    for ($attempt=0; $attempt -lt 12; $attempt++) {
        Start-Sleep -Seconds 1
        $listeners = @(Get-NetTCPConnection -LocalPort 9224 -State Listen -ErrorAction SilentlyContinue)
        if ($listeners.Count -gt 0) { break }
    }
    if ($listeners.Count -eq 0) { throw 'WhatsApp no inicio la conexion de prueba.' }
    if (@($listeners | Where-Object { $_.LocalAddress -notin @('127.0.0.1','::1') }).Count -gt 0) {
        throw 'Se detecto una conexion fuera de loopback. Lectura cancelada.'
    }
    $owners = @(Get-CimInstance Win32_Process -Filter "Name='msedgewebview2.exe'" |
        Where-Object { $_.CommandLine -match 'WhatsApp' } | Select-Object -ExpandProperty ProcessId)
    if (@($listeners | Where-Object { $_.OwningProcess -notin $owners }).Count -gt 0) {
        throw 'El puerto no pertenece al WebView de WhatsApp. Lectura cancelada.'
    }
    Start-Sleep -Seconds 3
    $env:WHATSAPP_CDP_PORT = '9224'
    & $PythonPath (Join-Path $PSScriptRoot 'probe_read_only.py') --report $ReportPath
    if ($LASTEXITCODE -ne 0) { throw 'No se completo la lectura. Consultar el estado del informe.' }
}
finally {
    $env:WHATSAPP_CDP_PORT = $originalPort
    try {
        if ($debugSession) { $debugSession.Dispose(); $optionsRemoved = $true }
    } catch {
        Write-Warning ('No se pudo confirmar la retirada de opciones: ' + $_.Exception.GetType().Name)
    } finally {
        if ($appRestarted) {
            Get-Process -Name 'WhatsApp.Root' -ErrorAction SilentlyContinue |
                Stop-Process -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
            Start-Process -FilePath 'whatsapp:'
            Start-Sleep -Seconds 2
        }
    }
    $portRemaining = @(Get-NetTCPConnection -LocalPort 9224 -State Listen -ErrorAction SilentlyContinue).Count -gt 0
    [PSCustomObject]@{
        TemporaryOptionsRemoved=$optionsRemoved;
        DebugListenerRemaining=$portRemaining;
        WhatsAppRunning=(@(Get-Process -Name 'WhatsApp.Root' -ErrorAction SilentlyContinue).Count -gt 0)
    } | ConvertTo-Json -Compress
    if ($appRestarted -and ($portRemaining -or -not $optionsRemoved)) {
        Write-Warning 'Limpieza no confirmada. Cerrar WhatsApp y revisar antes de repetir.'
    }
}
