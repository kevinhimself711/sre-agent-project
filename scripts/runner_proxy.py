"""Keep the pci-2 GitHub runner behind the local SSH-forwarded proxy.

The detached controller survives a terminal or Codex turn ending. Runtime state
and redacted transport logs stay under the ignored artifacts directory.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
PID_FILE = ARTIFACTS / "runner-proxy.pid"
STDOUT_LOG = ARTIFACTS / "runner-proxy-stdout.log"
STDERR_LOG = ARTIFACTS / "runner-proxy-stderr.log"
REMOTE_COMMAND = (
    'cd "$HOME/sre-agent-runner"; '
    'export PATH="$HOME/sre-agent-project/tools-venv/bin:$PATH"; '
    "exec ./run.sh"
)


def read_pid() -> int | None:
    try:
        return int(PID_FILE.read_text(encoding="ascii").strip())
    except (FileNotFoundError, ValueError):
        return None


def process_alive(pid: int | None) -> bool:
    if pid is None:
        return False
    if os.name == "nt":
        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))) and (
                exit_code.value == still_active
            )
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except (OSError, PermissionError):
        return False
    return True


def log_tail(path: Path, lines: int = 12) -> str:
    try:
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
    except FileNotFoundError:
        return ""


def start():
    existing = read_pid()
    if process_alive(existing):
        raise SystemExit(f"Runner proxy is already active (pid {existing})")

    ARTIFACTS.mkdir(exist_ok=True)
    start_offset = STDOUT_LOG.stat().st_size if STDOUT_LOG.exists() else 0
    command = [
        sys.executable,
        str(ROOT / "scripts/remote.py"),
        "--proxy",
        "run",
        REMOTE_COMMAND,
    ]
    options = (
        {"start_new_session": True}
        if os.name != "nt"
        else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS}
    )
    with STDOUT_LOG.open("ab", buffering=0) as stdout, STDERR_LOG.open("ab", buffering=0) as stderr:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            close_fds=True,
            **options,
        )
    PID_FILE.write_text(f"{process.pid}\n", encoding="ascii")

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            PID_FILE.unlink(missing_ok=True)
            raise SystemExit(
                f"Runner proxy exited with {process.returncode}:\n{log_tail(STDERR_LOG)}"
            )
        if STDOUT_LOG.exists():
            with STDOUT_LOG.open("rb") as output:
                output.seek(start_offset)
                if b"Listening for Jobs" in output.read():
                    print(f"Runner proxy active (pid {process.pid})")
                    return
        time.sleep(0.5)

    os.kill(process.pid, signal.SIGTERM)
    PID_FILE.unlink(missing_ok=True)
    raise SystemExit("Runner proxy did not reach the listening state within 30 seconds")


def status():
    pid = read_pid()
    state = "active" if process_alive(pid) else "inactive"
    print(f"Runner proxy {state}" + (f" (pid {pid})" if pid is not None else ""))
    tail = log_tail(STDOUT_LOG)
    if tail:
        print(tail)
    if state != "active":
        raise SystemExit(1)


def stop():
    pid = read_pid()
    if not process_alive(pid):
        PID_FILE.unlink(missing_ok=True)
        print("Runner proxy already inactive")
        return
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and process_alive(pid):
        time.sleep(0.2)
    if process_alive(pid):
        raise SystemExit(f"Runner proxy pid {pid} did not stop")
    PID_FILE.unlink(missing_ok=True)
    print(f"Runner proxy stopped (pid {pid})")


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("action", choices=("start", "status", "stop"))
    args = parser.parse_args()
    {"start": start, "status": status, "stop": stop}[args.action]()


if __name__ == "__main__":
    main()
