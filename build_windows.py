"""
build_windows.py — OPTIONAL convenience builder for Folder-Agent-Binding.

This is NOT required to use the tool. The recommended, source-first install runs
the .py files directly (see install_windows.ps1). This script only exists for
users who want standalone .exe wrappers.

What it does:
  1. pip-installs PyInstaller (build-time only; not a runtime dependency).
  2. Builds broker.exe and assign_to_agent.exe via PyInstaller --onefile,
     FROM THE AUDITED SOURCE in this repo.
  3. Prints SHA256 hashes so the user can verify their build matches source.
  4. Optionally writes the hashes into SECURITY.md (pass --update-security).

Safety note: you are building FROM SOURCE you can read. The resulting .exe is
yours, produced locally, and verifiable — not a downloaded opaque binary.
Run `bandit -r folder_agent_binding/` and `pip-audit` first if you want the
full safety picture (see THREAT_MODEL.md).

Usage:
    python build_windows.py
    python build_windows.py --update-security
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BROKER = ROOT / "folder_agent_binding" / "broker.py"
ASSIGN = ROOT / "folder_agent_binding" / "assign_to_agent.py"
DIST = ROOT / "dist"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def build_one(script: Path) -> Path:
    subprocess.run(
        [sys.executable, "-m", "PyInstaller",
         str(script), "--onefile", "--name", script.stem,
         "--distpath", str(DIST), "--workpath", str(ROOT / "build"),
         "--specpath", str(ROOT)],
        check=True,
    )
    return DIST / f"{script.stem}.exe"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--update-security", action="store_true",
                    help="write produced hashes into SECURITY.md")
    args = ap.parse_args()

    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"],
                   check=True)

    broker_exe = build_one(BROKER)
    assign_exe = build_one(ASSIGN)

    hashes = {
        "broker.exe": sha256(broker_exe),
        "assign_to_agent.exe": sha256(assign_exe),
    }
    print("\n=== Build complete (from audited source) ===")
    for name, h in hashes.items():
        print(f"  {name}\n    SHA256: {h}")

    if args.update_security:
        sec = ROOT / "SECURITY.md"
        if sec.exists():
            text = sec.read_text(encoding="utf-8")
            for name, h in hashes.items():
                text = text.replace(f"<filled-by-CI:{name}>", h)
                text = text.replace(f"<filled-by-CI>", h)  # generic fallback
            sec.write_text(text, encoding="utf-8")
            print(f"\nWrote hashes into {sec}")
        else:
            print("\nSECURITY.md not found; hashes printed above.")


if __name__ == "__main__":
    main()
