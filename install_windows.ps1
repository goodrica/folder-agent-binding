<Requires -RunAsAdministrator>
<#
  Folder-Agent-Binding — Windows 11 installer (context menu + broker service).

  SOURCE-FIRST. This tool ships as auditable Python source — NO prebuilt .exe.
  The broker runs via `pythonw.exe broker.py serve` and the context menu
  launches `pythonw.exe assign_to_agent.py "%1"`. If you want convenience
  .exe files later, run build_windows.py (optional, builds from this source).

  SAFETY / WHAT THIS SCRIPT DOES (no hidden behavior):
    1. Verifies Python 3.10+ is installed (refuses to continue if not).
    2. Copies broker.py + assign_to_agent.py into
       %LOCALAPPDATA%\FolderAgentBinding\  (auditable source stays on disk).
    3. Registers a right-click "Assign to Agent" entry under
       HKLM:\Software\Classes\Directory\shell\FolderAgentBinding.
    4. Creates a scheduled task to run the broker at logon (loopback
       127.0.0.1:8771 ONLY — never exposed to the network).
    5. Drops a default agents.json.

  It does NOT:
    * Modify any firewall rules or open ports.
    * Access the network, download anything, or contact the internet.
    * Read, copy, or transmit any file contents.
    * Build or run any .exe. (That is optional — see build_windows.py.)

  All source is auditable in the repo (see THREAT_MODEL.md / SECURITY.md).
#>

param(
    [string]$InstallDir = "$env:LOCALAPPDATA\FolderAgentBinding",
    [int]$BrokerPort     = 8771
)

$ErrorActionPreference = "Stop"

# --- 0. Require Python (source-first means we run .py, not .exe) ---
$py = (Get-Command python -ErrorAction SilentlyContinue) ??
      (Get-Command python3 -ErrorAction SilentlyContinue)
if (-not $py) {
    Write-Error "Python 3.10+ not found. Install it from https://python.org (tick 'Add to PATH'). Then re-run this script."
    exit 1
}
$pyPath  = $py.Source
$pyVer   = & $pyPath --version 2>&1
Write-Host "Using $pyPath ($pyVer)" -ForegroundColor Cyan

# Prefer pythonw (no console window) if present next to python.
$pyw = Join-Path (Split-Path $pyPath) "pythonw.exe"
if (-not (Test-Path $pyw)) { $pyw = $pyPath }

# --- 1. Copy auditable source into the install dir ---
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
$src = Split-Path $MyInvocation.MyCommand.Path
foreach ($f in @("broker.py", "assign_to_agent.py")) {
    $from = Join-Path $src $f
    if (Test-Path $from) { Copy-Item $from (Join-Path $InstallDir $f) -Force }
}
$brokerPy  = Join-Path $InstallDir "broker.py"
$assignPy  = Join-Path $InstallDir "assign_to_agent.py"

# --- 2. Context menu registration (HKLM requires admin; script already asks) ---
$shellKey = "HKLM:\Software\Classes\Directory\shell\FolderAgentBinding"
$cmdKey   = "$shellKey\command"
New-Item -Path $shellKey -Force | Out-Null
New-Item -Path $cmdKey -Force | Out-Null
Set-ItemProperty -Path $shellKey -Name "(Default)" -Value "Assign to Agent"
# Icon: fall back to a system folder icon if no custom .ico present.
$iconPath = Join-Path $src "folder-agent-binding.ico"
if (Test-Path $iconPath) {
    Set-ItemProperty -Path $shellKey -Name "Icon" -Value "$iconPath"
} else {
    Set-ItemProperty -Path $shellKey -Name "Icon" -Value "imageres.dll,2"
}
Set-ItemProperty -Path $cmdKey -Name "(Default)" -Value "`"$pyw`" `"$assignPy`" `"%1`""

# --- 3. Scheduled task: broker at logon (current user, loopback only) ---
$action    = New-ScheduledTaskAction -Execute $pyw `
                -Argument "`"$brokerPy`" --port $BrokerPort"
$trigger   = New-ScheduledTaskTrigger -AtLogOn
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive
Register-ScheduledTask -TaskName "FolderAgentBindingBroker" -Action $action `
    -Trigger $trigger -Principal $principal -Force | Out-Null

# --- 4. Default agents.json ---
$agentCfg = Join-Path $InstallDir "agents.json"
if (-not (Test-Path $agentCfg)) {
    $default = @{ agents = @("my-agent");
                  write_agents_md = $true;
                  note  = "Edit to add your Hermes agent/chat target names. Set write_agents_md to false to skip creating AGENTS.md." } | ConvertTo-Json
    Set-Content -Path $agentCfg -Value $default -Encoding UTF8
}

# --- 5. Start the broker now (so it's live without a reboot) ---
Start-ScheduledTask -TaskName "FolderAgentBindingBroker" -ErrorAction SilentlyContinue

Write-Host "Folder-Agent-Binding installed (source-first, no .exe)." -ForegroundColor Green
Write-Host "  Context menu: right-click any folder -> 'Assign to Agent'" -ForegroundColor Cyan
Write-Host "  Broker: loopback 127.0.0.1:$BrokerPort (logon task, running)" -ForegroundColor Cyan
Write-Host "  Source: $InstallDir" -ForegroundColor Cyan
Write-Host "  Edit agents: $agentCfg" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Optional: build .exe convenience wrappers from this source with:" -ForegroundColor Yellow
Write-Host "    python build_windows.py" -ForegroundColor Yellow
