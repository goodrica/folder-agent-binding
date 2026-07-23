# THREAT MODEL & SAFETY DESIGN

**Folder-Agent-Binding** is a local-only utility that lets a Windows 11 user
right-click a folder and register a "binding" between that folder and a Hermes
agent, then notify the agent over its existing (encrypted) Telegram channel.

This document exists so a third party can verify, in minutes, that the tool
does what it claims and nothing else. It is the centerpiece of our safety
story — see `SECURITY.md` for the independent-validation evidence.

---

## 1. What the tool can do (capability inventory)

| Capability | Mechanism | Network? |
|---|---|---|
| Register folder→agent binding (local JSON) | write `bindings.json` in `%LOCALAPPDATA%` | No |
| List / revoke bindings | read/modify local JSON | No |
| Describe folder *structure* (names + sizes only) | `os.scandir` on local path | No |
| Notify agent | `hermes send` CLI **or** printed message | Yes — Telegram API only, user-initiated |
| Serve local API | HTTP server bound to **127.0.0.1 only** | Loopback only |

## 2. What the tool CANNOT do (by design & by code)

- **No internet egress except the user-initiated Telegram notify.** The broker
  never phones home, never downloads, never uploads file contents.
- **No file contents are ever read or transmitted.** `describe_folder()` reads
  only entry names and byte sizes — never file bodies. No RAG ingestion happens
  in this tool; that is the agent's job, after the user shares a path it can
  reach.
- **AGENTS.md is user-opted.** Optionally writes a small marked section into
  the assigned folder's `AGENTS.md` (a standard convention read by Hermes,
  Claude Code, Cursor, etc.). The section is delimited by HTML comments, can
  be toggled off via `"write_agents_md": false` in `agents.json`, and is
  cleanly removed on unassign. No file contents are read — only this metadata
  section is written.
- **No 0.0.0.0 / public bind.** The listen address is hard-coded
  `127.0.0.1` in `broker.py::main()`. It cannot be changed via input, config,
  or env var. A remote host hitting the port receives `403`.
- **No secrets handled.** The tool stores no tokens/keys. Hermes credentials
  stay in the user's Hermes config; the broker calls the `hermes` CLI which
  reads them from there. If the CLI is absent, the message is printed for the
  user to paste manually.
- **No privilege escalation.** Installer uses a per-user scheduled task + a
  standard shell registry key. No system service, no driver, no admin-only FS
  writes (admin is only needed for the HKLM context-menu key, a one-time reg
  write, not a persistent privilege).
- **No persistence beyond the stated artifacts.** Uninstall removes the reg key,
  scheduled task, and `%LOCALAPPDATA%\FolderAgentBinding`.

## 3. Attack surface analysis

| Threat | Likelihood | Mitigation |
|---|---|---|
| Remote attacker reaches broker | None | Loopback-only bind; 403 for non-loopback source IP. |
| Malicious folder name injects into notify | Low | Message is a plain string to the agent; no shell/exec on the path. Path is never executed. |
| Local malware abuses loopback API to spam agent | Low | API only writes local JSON + sends one notify. No destructive capability. Revocable. |
| Tampered EXE exfiltrates files | Low (if user verifies build) | Reproducible PyInstaller build from audited source; SBOM + hash published; see SECURITY.md. |
| `agents.json` tampering | Low | Only changes which agent names are offered; no code execution. |

## 4. Data flow (end to end)

```
[Windows Explorer right-click]
        |
        v
[assign_to_agent.exe]  --(argv: folder path, local only)-->
[Broker @127.0.0.1:8771]  --writes-->  bindings.json (local)
        |                                 |
        | (user-initiated)                +-- describe_folder() [names+sizes only]
        v
[hermes send --agent X]  -->  Telegram (encrypted)  -->  Hermes bot
```

No arrow crosses the loopback boundary except the single, user-initiated
Telegram notification. File contents never leave the machine via this tool.

## 5. How to independently verify

1. **Read the source.** It is ~300 lines of dependency-free Python.
2. **Run the static analyzer:** `bandit -r folder_agent_binding/` → see
   `SECURITY.md` for the published clean report.
3. **Check dependencies:** `pip-audit` against the (empty) runtime deps.
4. **Reproduce the build:** `pyinstaller broker.py --onefile` and compare the
   SHA256 to the published artifact hash.
5. **Network test:** while running, `nmap` / `Test-NetConnection` from another
   machine to the broker port → should be filtered/refused.

---

*This tool is deliberately boring. Its safety comes from doing less, not from
complex defenses.*
