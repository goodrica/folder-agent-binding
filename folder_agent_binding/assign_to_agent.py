"""
Windows 11 Explorer context-menu entry point for Folder-Agent-Binding.

This is the program that runs when the user right-clicks a folder and picks
"Assign to Agent". It is a STANDALONE Windows executable (built with
PyInstaller, zero third-party runtime deps). On Linux/macOS it is unused.

What it does:
  1. Receives the folder path via argv (Explorer passes it through the
     registry-shell registration).
  2. Shows a tiny selection dialog (Tk, stdlib) listing the user's configured
     Hermes agents (read from a LOCAL config file — no network, no secrets).
  3. POSTs {action:"assign", agent, folder} to the LOCAL broker at
     127.0.0.1:8771. That's it. No internet egress except the broker's
     Telegram notify (user-initiated).

Safety notes:
  * Talks only to 127.0.0.1. Never contacts any remote host directly.
  * Contains no tokens/keys. Agent list comes from a local JSON the user edits.
  * The folder path is sent ONLY to the local broker; file contents are never
    read or transmitted by this program.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import sys
import urllib.parse
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    _HAVE_TK = True
except ImportError:  # headless / non-Windows dev
    _HAVE_TK = False

CONFIG_PATH = Path(os.environ.get("LOCALAPPDATA", Path.home())) / \
    "FolderAgentBinding" / "agents.json"
BROKER_HOST = "127.0.0.1"
BROKER_PORT = 8771


def load_agents() -> list[str]:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("agents", [])
    except (OSError, json.JSONDecodeError):
        return []


def load_config() -> dict:
    """Load agents.json config, returning full dict (agents + settings)."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def ensure_config() -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        default = {
            "agents": [],
            "write_agents_md": True,
            "note": "Edit this file to add/remove agent names. These must be "
                    "valid Hermes agent/chat targets the broker can message. "
                    "Set write_agents_md to false to skip creating AGENTS.md.",
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(default, fh, indent=2)


def send_assign(agent: str, folder: str, write_agents_md: bool = True) -> bool:
    payload = json.dumps(
        {"action": "assign", "agent": agent, "folder": folder,
         "write_agents_md": write_agents_md}
    ).encode("utf-8")
    conn = None
    try:
        conn = http.client.HTTPConnection(BROKER_HOST, BROKER_PORT, timeout=5)
        conn.request("POST", "/", body=payload,
                     headers={"Content-Type": "application/json"})
        with conn.getresponse() as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return bool(body.get("ok"))
    except (OSError, ValueError) as e:
        print(f"assign failed: {e}", file=sys.stderr)
        return False
    finally:
        if conn:
            conn.close()


def query_bindings(folder: str) -> list:
    """Ask the local broker which agents this folder is already bound to."""
    conn = None
    try:
        conn = http.client.HTTPConnection(BROKER_HOST, BROKER_PORT, timeout=5)
        conn.request("GET", f"/bindings?folder={urllib.parse.quote(folder)}")
        with conn.getresponse() as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("bindings", [])
    except (OSError, ValueError):
        return []
    finally:
        if conn:
            conn.close()


def send_revoke(agent: str, folder: str, remove_agents_md: bool = True) -> bool:
    payload = json.dumps(
        {"action": "revoke", "agent": agent, "folder": folder,
         "remove_agents_md": remove_agents_md}
    ).encode("utf-8")
    conn = None
    try:
        conn = http.client.HTTPConnection(BROKER_HOST, BROKER_PORT, timeout=5)
        conn.request("POST", "/", body=payload,
                     headers={"Content-Type": "application/json"})
        with conn.getresponse() as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return bool(body.get("ok"))
    except (OSError, ValueError):
        return False
    finally:
        if conn:
            conn.close()


def pick_agent(agents: list[str], folder: str,
               write_agents_md_default: bool = True) -> dict | None:
    if not _HAVE_TK:
        # Non-interactive fallback: print choices, require agent via argv.
        existing = query_bindings(folder)
        if existing:
            print("Already assigned to:", [b["agent"] for b in existing])
        print("Available agents:", agents)
        return None

    existing = query_bindings(folder)
    assigned = [b["agent"] for b in existing]
    choice: dict = {}

    def do_assign():
        choice["action"] = "assign"
        choice["agent"] = combo.get()
        choice["write_agents_md"] = agents_md_var.get()
        root.destroy()

    def do_revoke():
        sel = combo.get()
        if sel in assigned:
            choice["action"] = "revoke"
            choice["agent"] = sel
            root.destroy()

    root = tk.Tk()
    root.title("Assign Folder to Agent")
    root.geometry("440x220")
    tk.Label(root, text="Assign folder to a Hermes agent:").pack(pady=(12, 4))
    tk.Label(root, text=folder, fg="gray", wraplength=400).pack(pady=(0, 6))

    if assigned:
        tk.Label(root, text=f"⚠ Already assigned to: {', '.join(assigned)}",
                 fg="darkorange", wraplength=400).pack(pady=(0, 6))
    else:
        tk.Label(root, text="Not currently assigned to any agent.",
                 fg="green", wraplength=400).pack(pady=(0, 6))

    combo = ttk.Combobox(root, values=agents, state="readonly")
    if assigned and assigned[0] in agents:
        combo.set(assigned[0])  # preselect the already-assigned agent
    elif agents:
        combo.current(0)
    combo.pack(fill="x", padx=20, pady=(0, 6))

    agents_md_var = tk.BooleanVar(value=write_agents_md_default)
    agents_md_cb = tk.Checkbutton(
        root, text="Write AGENTS.md (persistent context in folder)",
        variable=agents_md_var,
    )
    agents_md_cb.pack(padx=20, pady=(0, 8))

    btn_frame = tk.Frame(root)
    btn_frame.pack()
    tk.Button(btn_frame, text="Assign", command=do_assign).pack(side="left", padx=8)
    revoke_btn = tk.Button(btn_frame, text="Unassign", command=do_revoke,
                           state="normal" if assigned else "disabled")
    revoke_btn.pack(side="left", padx=8)
    root.mainloop()
    return choice if choice else None


def main() -> None:
    ap = argparse.ArgumentParser(description="Folder-Agent-Binding agent picker")
    ap.add_argument("folder", nargs="?", help="folder path to assign")
    ap.add_argument("--agent", default="", help="agent name (skips GUI)")
    ap.add_argument("--revoke", action="store_true", help="revoke instead of assign")
    args = ap.parse_args()

    folder = args.folder
    if not folder:
        print("usage: assign_to_agent.py <folder_path> [--agent NAME] [--revoke]",
              file=sys.stderr)
        sys.exit(2)
    ensure_config()
    agents = load_agents()
    if not agents:
        print("No agents configured. Edit:", CONFIG_PATH, file=sys.stderr)
        sys.exit(1)

    # Headless: --agent lets CLI/automation bypass the GUI entirely.
    config = load_config()
    write_agents_md_flag = config.get("write_agents_md", True)
    if args.agent:
        if args.revoke:
            ok = send_revoke(args.agent, folder, remove_agents_md=write_agents_md_flag)
            msg = f"Unassigned from {args.agent} ✓" if ok else "Revoke failed — is the broker running?"
        else:
            ok = send_assign(args.agent, folder, write_agents_md=write_agents_md_flag)
            msg = f"Assigned to {args.agent} ✓" if ok else "Assign failed — is the broker running?"
        print(msg)
        sys.exit(0 if ok else 1)

    result = pick_agent(agents, folder, write_agents_md_default=write_agents_md_flag)
    if not result:
        sys.exit(1)
    # result dict carries action + agent (set inside the GUI)
    action = result.get("action", "assign")
    agent = result["agent"]
    write_md = result.get("write_agents_md", True)
    if action == "revoke":
        ok = send_revoke(agent, folder, remove_agents_md=write_md)
        msg = f"Unassigned from {agent} ✓" if ok else "Revoke failed — is the broker running?"
    else:
        ok = send_assign(agent, folder, write_agents_md=write_md)
        msg = f"Assigned to {agent} ✓" if ok else "Assign failed — is the broker running?"
    if _HAVE_TK:
        messagebox.showinfo("Folder-Agent-Binding", msg)
    else:
        print(msg)
