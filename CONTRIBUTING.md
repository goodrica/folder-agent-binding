# Contributing

Thanks for wanting to build on Folder-Agent-Binding. It's free, MIT-licensed,
and open to the world.

## Principles (non-negotiable)

- **Local-first, loopback-only.** Never introduce a 0.0.0.0 bind or remote
  egress without explicit, documented, opt-in user consent.
- **No secrets in the tool.** Tokens/keys stay in the user's Hermes config.
- **No third-party runtime dependencies.** Stdlib only. If you truly need a
  library, open an issue first — it must survive `pip-audit` and the zero-dep
  proof in CI.
- **No telemetry.** The tool must not contact the internet except the
  user-initiated agent notify.

## How to contribute

1. Fork, branch (`feat/...`, `fix/...`).
2. Keep it stdlib-only. Run `bandit -r folder_agent_binding/` (expect ≤ Low).
3. Add/adjust tests in the functional style (broker assign/revoke/status).
4. Open a PR. CI runs Bandit + zero-dep proof + (build) hash check.
5. Update `THREAT_MODEL.md` / `SECURITY.md` if behavior changes.

## Ideas we'd love

- "Unassign" as a second context-menu entry (currently in the GUI).
- Cross-platform file-manager plugins (Finder, Nautilus, Double Commander).
- Optional local file-server mode for cloud AIs (Claude/Codex) with scoped tokens.
- The agent-token attribution economy (separate repo, also open).

## Code of conduct

Be kind, be terse, ship working things. See you in the issues.
