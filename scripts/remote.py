"""Small SSH transport for the two personal nodes; credentials stay untracked.

Examples: python scripts/remote.py run 'uname -sr'
          python scripts/remote.py put scripts/bootstrap_node.sh sre-agent-project/bootstrap_node.sh
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import socket
import select
import sys
import threading
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
warnings.filterwarnings("ignore", module="paramiko.*")
try:
    import paramiko
except ImportError:
    sys.path.insert(0, str(ROOT / ".research/python-deps"))
    import paramiko


def connect(node: str):
    raw = (ROOT / "docs/Computing Resources" / f"{node} info.txt").read_text(
        encoding="utf-8-sig"
    )
    hosts = re.findall(r"(?:\d{1,3}\.){3}\d{1,3}", raw)
    ports = [int(x) for x in re.findall(r"(?im)^Port:\s*(\d+)", raw)]
    user = re.search(r"(?im)^User:\s*(.+)", raw).group(1).strip()
    password = re.search(r"(?im)^pwd:\s*(.+)", raw).group(1).strip()
    for host, port in zip(hosts, ports):
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                host,
                port=port,
                username=user,
                password=password,
                timeout=8,
                banner_timeout=10,
                auth_timeout=10,
                look_for_keys=False,
                allow_agent=False,
            )
            return client, password
        except (OSError, paramiko.SSHException):
            client.close()
    raise RuntimeError(f"Cannot connect to {node}; credentials and endpoint omitted")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--node", default="pci-2", choices=["pci-1", "pci-2"])
    parser.add_argument(
        "--bailian",
        action="store_true",
        help="Inject API key into remote process environment",
    )
    parser.add_argument(
        "--proxy",
        action="store_true",
        help="Forward the local HTTP proxy over this SSH session",
    )
    parser.add_argument("action", choices=["run", "sudo", "put", "get"])
    parser.add_argument("source")
    parser.add_argument("destination", nargs="?")
    args = parser.parse_args()
    client, password = connect(args.node)
    secrets = [password]
    try:
        if args.proxy:
            transport = client.get_transport()
            proxy_port = transport.request_port_forward("127.0.0.1", 0)

            def relay(channel):
                try:
                    with socket.create_connection(
                        ("127.0.0.1", 7897), timeout=15
                    ) as sock:
                        while True:
                            readable, _, _ = select.select([sock, channel], [], [], 30)
                            for source in readable:
                                data = source.recv(65536)
                                if not data:
                                    return
                                (channel if source is sock else sock).sendall(data)
                finally:
                    channel.close()

            def accept():
                while transport.is_active():
                    channel = transport.accept(1)
                    if channel is not None:
                        threading.Thread(
                            target=relay, args=(channel,), daemon=True
                        ).start()

            threading.Thread(target=accept, daemon=True).start()
        if args.action in ("put", "get"):
            if not args.destination:
                parser.error("destination required")
            with client.open_sftp() as sftp:
                if args.action == "put":
                    sftp.put(args.source, args.destination)
                else:
                    Path(args.destination).parent.mkdir(parents=True, exist_ok=True)
                    sftp.get(args.source, args.destination)
            print(f"{args.action}: {args.destination}")
            return
        command = args.source
        payload = None
        if args.action == "sudo":
            command = 'sudo -S -p "" -- bash -c ' + shlex.quote(command)
            payload = password + "\n"
        elif args.bailian or args.proxy:
            env = {}
            if args.bailian:
                key_text = (ROOT / "Bailian API.txt").read_text(encoding="utf-8-sig")
                key = re.search(r"sk-[A-Za-z0-9_-]+", key_text).group()
                secrets.append(key)
                env.update(
                    {
                        name: key
                        for name in [
                            "DASHSCOPE_API_KEY",
                            "OPENAI_API_KEY",
                            "AGENT_API_KEY",
                            "JUDGE_API_KEY",
                        ]
                    }
                )
            if args.proxy:
                env.update(
                    {
                        name: f"http://127.0.0.1:{proxy_port}"
                        for name in [
                            "http_proxy",
                            "https_proxy",
                            "HTTP_PROXY",
                            "HTTPS_PROXY",
                        ]
                    }
                )
                env["no_proxy"] = (
                    "localhost,127.0.0.1,::1,.cluster.local,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
                )
            code = 'import sys,json,os; p=json.loads(sys.stdin.readline()); os.environ.update(p["env"]); os.execvp("bash",["bash","-lc",p["command"]])'
            command = "python3 -c " + shlex.quote(code)
            payload = json.dumps({"env": env, "command": args.source}) + "\n"
        stdin, stdout, stderr = client.exec_command(command)
        if payload:
            stdin.write(payload)
            stdin.flush()
        stdin.channel.shutdown_write()
        channel = stdout.channel
        while True:
            for ready, receive in (
                (channel.recv_ready, channel.recv),
                (channel.recv_stderr_ready, channel.recv_stderr),
            ):
                if ready():
                    content = receive(65536).decode("utf-8", errors="replace")
                    for secret in secrets:
                        content = content.replace(secret, "[REDACTED]")
                    content = re.sub(r"\bsk-[A-Za-z0-9_-]{16,}", "[REDACTED]", content)
                    print(content, end="", flush=True)
            if (
                channel.exit_status_ready()
                and not channel.recv_ready()
                and not channel.recv_stderr_ready()
            ):
                break
            time.sleep(0.1)
        raise SystemExit(channel.recv_exit_status())
    finally:
        client.close()


if __name__ == "__main__":
    main()
