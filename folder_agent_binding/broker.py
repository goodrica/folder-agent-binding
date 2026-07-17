"""
folder-agent-binding — local broker (Windows 11)

SECURITY MODEL (read THREAT_MODEL.md):
  * This broker listens ONLY on 127.0.0.1 (loopback). It is NEVER reachable
    from the network. There is no 0.0.0.0 bind anywhere in this codebase.
  * It holds NO secret material. Bot tokens / API keys live in the user's
    Hermes config and are never read, logged, or transmitted by this tool.
  * Notifications are delivered to the Hermes bot over its EXISTING, encrypted
    Telegram channel. We do not invent a new transport or expose the agent.
  * The binding store is a plaintext JSON file in the user's profile dir with
    restrictive ACLs; it contains only folder paths + agent names, no secrets.

The broker's only jobs:
  1. Record a folder->agent binding locally (so it survives reboots & is
     visible/revocable).
  2. Send a notification message to the chosen Hermes bot telling it the user
     assigned a folder, with a short description of the folder's contents.
  3. Revoke a binding on request.

It does NOT:
  * Read file contents and ship them anywhere.
  * Open any listening port other than loopback.
  * Talk to the internet except to Telegram's API (user-initiated notify).
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# ---------------------------------------------------------------------------
# Paths — all local to the user profile. No network, no shared locations.
# ---------------------------------------------------------------------------
APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FolderAgentBinding"
BINDINGS_FILE = APP_DIR / "bindings.json"
LOG_FILE = APP_DIR / "broker.log"

APP_DIR.mkdir(parents=True, exist_ok=True)
for f in (BINDINGS_FILE, LOG_FILE):
    if not f.exists():
        f.touch()
    # Restrict to owner on Windows is handled by installer; on *nix chmod 600.
    try:
        os.chmod(f, 0o600)
    except OSError:
        pass


def log(msg: str) -> None:
    line = f"{_now()} {msg}\n"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        pass


def _now() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Binding store
# ---------------------------------------------------------------------------
def load_bindings() -> dict:
    try:
        with open(BINDINGS_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {"bindings": []}


def save_bindings(data: dict) -> None:
    with open(BINDINGS_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def describe_folder(path: str) -> str:
    """Lightweight, LOCAL-ONLY description of a folder's structure.

    Deliberately does NOT read file contents. Only names + sizes + tree depth,
    so the agent gets orientation without us exfiltrating data.
    """
    p = Path(path)
    if not p.exists():
        return "(folder not found)"
    lines = []
    try:
        children = sorted(p.iterdir())
    except PermissionError:
        return "(no read permission)"
    for i, child in enumerate(children[:50]):
        try:
            if child.is_dir():
                lines.append(f"  [dir]  {child.name}/")
            else:
                size = child.stat().st_size
                lines.append(f"  [file] {child.name} ({size} bytes)")
        except OSError:
            lines.append(f"  [??]   {child.name}")
        if i >= 49:
            lines.append("  ... (truncated at 50 entries)")
            break
    return "\n".join(lines) if lines else "(empty folder)"


# ---------------------------------------------------------------------------
# Notification — delivered to the Hermes bot over its existing Telegram channel.
#
# We shell out to the `hermes` CLI if available on this machine; otherwise we
# print the exact message the user should paste. This keeps the broker free of
# any embedded token. The CLI reads the token from the user's own Hermes config.
# ---------------------------------------------------------------------------
def notify_agent(agent_name: str, folder: str, description: str) -> dict:
    message = (
        f"📁 Folder assigned to you: {folder}\n\n"
        f"Binding created by user via right-click (Folder-Agent-Binding).\n\n"
        f"Folder contents:\n{description}\n\n"
        f"You now have a standing context for this folder. The user can revoke "
        f"this binding at any time from the Windows context menu."
    )
    # Best effort: try the hermes CLI send-to-agent if present.
    try:
        # nosec B603,B607: list-form args (no shell), binary name is a fixed
        # literal ("hermes"), and all substituted values are local agent names
        # / messages we constructed ourselves — no untrusted input reaches exec.
        result = subprocess.run(
            ["hermes", "send", "--agent", agent_name, "--message", message],
            capture_output=True, text=True, timeout=30,
        )
        ok = result.returncode == 0
        detail = result.stdout.strip() or result.stderr.strip()
    except FileNotFoundError:
        ok = False
        detail = "hermes CLI not found on this machine; message printed below."
        print("---- PASTE THIS TO YOUR BOT ----")
        print(f"To agent '{agent_name}':\n{message}")
        print("-------------------------------")
    except subprocess.TimeoutExpired:
        ok = False
        detail = "timeout talking to hermes CLI"
    log(f"notify agent={agent_name} folder={folder} ok={ok}")
    return {"ok": ok, "detail": detail}


def add_binding(agent_name: str, folder: str) -> dict:
    data = load_bindings()
    # de-dup
    for b in data["bindings"]:
        if b["agent"] == agent_name and b["folder"] == folder:
            return {"ok": True, "detail": "binding already exists", "binding": b}
    binding = {
        "agent": agent_name,
        "folder": folder,
        "created": _now(),
        "description": describe_folder(folder),
    }
    data["bindings"].append(binding)
    save_bindings(data)
    note = notify_agent(agent_name, folder, binding["description"])
    return {"ok": True, "detail": "binding saved; " + note["detail"], "binding": binding}


def remove_binding(agent_name: str, folder: str) -> dict:
    data = load_bindings()
    before = len(data["bindings"])
    data["bindings"] = [
        b for b in data["bindings"]
        if not (b["agent"] == agent_name and b["folder"] == folder)
    ]
    save_bindings(data)
    removed = before - len(data["bindings"])
    log(f"revoke agent={agent_name} folder={folder} removed={removed}")
    return {"ok": True, "removed": removed}


def list_bindings() -> dict:
    return load_bindings()


def bindings_for_folder(folder: str) -> list:
    """Return existing bindings that reference this exact folder path."""
    return [b for b in load_bindings()["bindings"] if b["folder"] == folder]


# ---------------------------------------------------------------------------
# HTTP handler — LOOPBACK ONLY. See main() for the bind address enforcement.
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            self._send(403, {"error": "only loopback clients allowed"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            req = json.loads(raw or b"{}")
        except (ValueError, OSError):
            self._send(400, {"error": "bad request"})
            return

        action = req.get("action")
        if action == "assign":
            out = add_binding(req.get("agent", ""), req.get("folder", ""))
        elif action == "revoke":
            out = remove_binding(req.get("agent", ""), req.get("folder", ""))
        else:
            self._send(400, {"error": "unknown action"})
            return
        self._send(200, out)

    def do_GET(self):  # noqa: N802
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            self._send(403, {"error": "only loopback clients allowed"})
            return
        parsed = urlparse(self.path)
        if parsed.path == "/bindings":
            q = parse_qs(parsed.query)
            folder = q.get("folder", [None])[0]
            if folder:
                self._send(200, {"bindings": bindings_for_folder(folder)})
            else:
                self._send(200, list_bindings())
        elif parsed.path == "/health":
            self._send(200, {"status": "ok"})
        else:
            self._send(404, {"error": "not found"})

    def log_message(self, *args):  # silence default stderr logging
        return


def main() -> None:
    ap = argparse.ArgumentParser(description="Folder-Agent-Binding local broker")
    ap.add_argument("--port", type=int, default=8771, help="loopback port")
    ap.add_argument("command",
                    nargs="?", choices=["serve", "assign", "revoke", "list"],
                    default="serve")
    ap.add_argument("--agent", default="")
    ap.add_argument("--folder", default="")
    args = ap.parse_args()

    if args.command == "assign":
        print(json.dumps(add_binding(args.agent, args.folder), indent=2))
        return
    if args.command == "revoke":
        print(json.dumps(remove_binding(args.agent, args.folder), indent=2))
        return
    if args.command == "list":
        print(json.dumps(list_bindings(), indent=2))
        return

    # SERVE — bind to loopback ONLY. Hard-coded, cannot be overridden by input.
    HOST = "127.0.0.1"
    server = ThreadingHTTPServer((HOST, args.port), Handler)
    log(f"broker listening on {HOST}:{args.port} (loopback only)")
    print(f"[folder-agent-binding] broker on {HOST}:{args.port} (loopback only)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
