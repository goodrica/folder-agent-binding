# Folder-Agent-Binding

> **🆓 Free forever. Open source. Local-only. No account, no telemetry, no catch.**
> MIT-licensed — build on it, ship it, rebrand it. See [FREE_FOREVER.md](FREE_FOREVER.md).
> 🌐 Site: https://goodrica.github.io/folder-agent-binding/

> Right-click any folder in Windows 11 Explorer → "Assign to Agent" → pick a
> Hermes agent (Goodybot, Dottie, Trader, or your own). The agent gets notified
> over its existing encrypted Telegram channel and gains a **standing context**
> for that folder.

This is a small, **local-only** utility that mirrors how people already think:
*"this folder is the taxes stuff"* → now your agent knows that too. It is the
human-organizational layer that makes RAG and agent memory actually useful —
folders become scoped, persistent agent contexts instead of a flat file dump.

## Why this is safe (tl;dr)

- **Loopback only.** The broker binds to `127.0.0.1` — hard-coded, not
  configurable. Never reachable from the network. See `THREAT_MODEL.md`.
- **No secrets.** The tool stores no tokens/keys. It calls the `hermes` CLI,
  which reads credentials from your own Hermes config.
- **No file exfiltration.** Only folder *names and sizes* are summarized locally.
  File *contents* are never read or transmitted by this tool.
- **Zero runtime dependencies.** Pure Python stdlib. `pip-audit` → 0 CVEs.
- **Independently verifiable.** `bandit`, `pip-audit`, SBOM, reproducible build —
  all in CI. See `SECURITY.md`.

## Architecture

```
Explorer right-click
   -> assign_to_agent.py (stdlib Tk GUI, picks agent)
   -> POST 127.0.0.1:8771  {action:"assign", agent, folder}
   -> broker.py  (writes bindings.json, describes folder structure)
   -> hermes send --agent X  ->  Telegram (encrypted)  ->  Hermes bot
```

No arrow leaves the machine except the single, user-initiated Telegram message.

## Install (Windows 11) — source-first, no .exe

```powershell
# Prereq: Python 3.10+ on PATH (python.org, tick "Add to PATH").
# Run in an elevated PowerShell (admin) from the repo root:
.\install_windows.ps1
```

This copies the auditable `.py` source into
`%LOCALAPPDATA%\FolderAgentBinding\`, registers the context-menu entry, creates
a logon scheduled task that runs `pythonw broker.py serve` (loopback only), and
drops a default `agents.json`. Edit
`%LOCALAPPDATA%\FolderAgentBinding\agents.json` to set your agent names.

> **No prebuilt binaries.** The tool runs as readable Python source — you can
> inspect every line. If you want standalone `.exe` wrappers for convenience,
> build them yourself from this source with `python build_windows.py`
> (optional; produces SHA256 hashes you can verify). See `SECURITY.md`.

## Usage

1. Right-click any folder in Explorer.
2. Click **"Assign to Agent"**.
3. Pick the Hermes agent from the dropdown.
4. The agent receives a notification: *"Folder assigned to you: <path>"* with a
   structural summary. It now has standing context for that folder.
5. Revoke anytime via `broker.py revoke --agent X --folder Y` (or the planned
   "Unassign" context-menu item).

## Files

| File | Role |
|---|---|
| `folder_agent_binding/broker.py` | Local loopback broker + binding store |
| `folder_agent_binding/assign_to_agent.py` | Explorer entry point (Tk picker) |
| `install_windows.ps1` | Context-menu + broker installer |
| `THREAT_MODEL.md` | Full capability/inability + attack-surface analysis |
| `SECURITY.md` | Third-party validation evidence & reproduction steps |
| `.github/workflows/validate.yml` | Bandit + pip-audit + SBOM in CI |

## Roadmap

- [ ] "Unassign" context-menu item (revoke)
- [ ] Optional local file-server mode for cloud AIs (Claude/Codex) with scoped tokens
- [ ] Cross-platform file-manager plugins (Finder, Nautilus, Double Commander)

## License

MIT — see `LICENSE`.
