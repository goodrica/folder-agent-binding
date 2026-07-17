<Requires -RunAsAdministrator>
<#
  Folder-Agent-Binding — Windows 11 installer (context menu + broker service).

  SAFETY / WHAT THIS SCRIPT DOES (no hidden behavior):
    1. Registers a right-click "Assign to Agent" entry under
       HKLM:\Software\Classes\Directory\shell\FolderAgentBinding
       that launches the bundled assign_to_agent.exe with the folder path.
    2. Creates a scheduled task to run the local broker at logon
       (loopback 127.0.0.1:8771 ONLY — never exposed to the network).
    3. Drops a default agents.json in %LOCALAPPDATA%\FolderAgentBinding.

  It does NOT:
    * Modify any firewall rules or open ports.
    * Access the network, download anything, or contact the internet.
    * Read, copy, or transmit any file contents.
    * Install services outside the current user's context.

  The broker binary is built from broker.py via PyInstaller with --onefile.
  All source is auditable in the repo (see THREAT_MODEL.md).
#>

param(
    [string]$InstallDir = "$env:LOCALAPPDATA\FolderAgentBinding",
    [string]$BrokerExe   = "$env:LOCALAPPDATA\FolderAgentBinding\broker.exe",
    [string]$AssignExe   = "$env:LOCALAPPDATA\FolderAgentBinding\assign_to_agent.exe",
    [int]$BrokerPort     = 8771
)

$ErrorActionPreference = "Stop"

# --- 1. Context menu registration (HKLM requires admin; script already asks) ---
$shellKey = "HKLM:\Software\Classes\Directory\shell\FolderAgentBinding"
$cmdKey   = "$shellKey\command"
New-Item -Path $shellKey -Force | Out-Null
New-Item -Path $cmdKey -Force | Out-Null
Set-ItemProperty -Path $shellKey -Name "(Default)" -Value "Assign to Agent"
Set-ItemProperty -Path $shellKey -Name "Icon" -Value "$AssignExe,0"
Set-ItemProperty -Path $cmdKey -Name "(Default)" -Value "`"$AssignExe`" `"%1`""

# --- 2. Scheduled task: broker at logon (current user, loopback only) ---
$action = New-ScheduledTaskAction -Execute $BrokerExe -Argument "--port $BrokerPort"
$trigger = New-ScheduledTaskTrigger -AtLogOn
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive
Register-ScheduledTask -TaskName "FolderAgentBindingBroker" -Action $action `
    -Trigger $trigger -Principal $principal -Force | Out-Null

# --- 3. Default agents.json ---
$agentCfg = Join-Path $InstallDir "agents.json"
if (-not (Test-Path $agentCfg)) {
    $default = @{ agents = @("Goodybot", "Dottie", "Trader");
                  note  = "Edit to add/remove Hermes agent names." } | ConvertTo-Json
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    Set-Content -Path $agentCfg -Value $default -Encoding UTF8
}

Write-Host "Folder-Agent-Binding installed." -ForegroundColor Green
Write-Host "  Context menu: right-click any folder -> 'Assign to Agent'" -ForegroundColor Cyan
Write-Host "  Broker: loopback 127.0.0.1:$BrokerPort (logon task)" -ForegroundColor Cyan
Write-Host "  Edit agents: $agentCfg" -ForegroundColor Cyan
