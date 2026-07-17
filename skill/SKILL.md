---
name: folder-agent-binding
description: Install and use Folder-Agent-Binding — right-click any folder in Windows 11 Explorer to assign it as a standing context to a Hermes agent (Goodybot/Dottie/Trader or any profile). Local-only, open source, no secrets handled, loopback-only network. Use when the user wants to bind folders to agents via the Explorer context menu, or asks about folder->agent assignment, RAG context organization, or the Folder-Agent-Binding tool.
category: software-development
---

# Folder-Agent-Binding (Hermes skill)

Turns "this folder is the taxes stuff" into "your agent now knows that too."
Right-click a folder in Windows 11 Explorer → "Assign to Agent" → the chosen
Hermes agent gets a notification over its existing encrypted Telegram channel
and gains a **standing context** for that folder. Mirrors how humans already
organize — the missing organizational layer for agent memory / RAG.

## Why it's safe (verify yourself)
- Loopback-only broker (127.0.0.1, hard-coded — never public).
- No secrets: calls the `hermes` CLI, which reads the user's own config.
- No file contents read/transmitted — only folder names + sizes summarized.
- Zero third-party runtime deps (stdlib only) → `pip-audit` = 0 CVEs.
- Bandit static analysis: 0 High/Medium. Full proof in THREAT_MODEL.md / SECURITY.md.

## Install (Windows 11, elevated PowerShell, from repo root)
```powershell
# Prereq: Python 3.10+ on PATH.
.\install_windows.ps1
```
Copies the auditable `.py` source into `%LOCALAPPDATA%\FolderAgentBinding\`,
registers the context-menu entry, and runs the broker via
`pythonw broker.py serve` (loopback only). **No prebuilt binaries** — the tool
runs as readable source. Optional `.exe` wrappers can be built from source with
`python build_windows.py`.

## Usage
1. Right-click any folder in Explorer → **"Assign to Agent"**.
2. The dialog shows whether the folder is **already assigned** (to which agents)
   and lets you Assign or Unassign.
3. The agent receives: *"Folder assigned to you: <path>"* + a structural summary.
4. Revoke anytime via the same dialog's **Unassign** button.

## Files in this skill
- `broker.py` — local loopback broker + binding store
- `assign_to_agent.py` — Explorer entry point (Tk picker w/ status)
- `install_windows.ps1` — context-menu + broker installer
- `THREAT_MODEL.md`, `SECURITY.md`, `README.md`, `LICENSE` (MIT, free forever)

## Source of truth
Full repo (issues, CI validation, website): https://github.com/<your-org>/folder-agent-binding
The tool is FREE FOREVER, MIT-licensed, and open for anyone to build on.

## Notes / limitations (v1)
- Notify path uses the `hermes send` CLI; if absent, prints the message to paste.
- Bot runs wherever your Hermes gateway runs; the Windows side only records the
  binding + notifies. Actual cross-machine file reads need a path the agent can
  reach (network share / paste). Phase 2 adds Claude/Codex + local file-server.
- "Unassign" is in the GUI; CLI revoke: `broker.py revoke --agent X --folder Y`.
