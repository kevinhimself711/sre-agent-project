"""Temporary setup-only network repair for the frozen campaign's closed init proxies."""
import hashlib
import ipaddress
import json
import os
import select
import socket
import socketserver
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

root = Path(os.environ["SRE_PROJECT_ROOT"])
k = [str(root / "bin/kubectl"), "--kubeconfig", str(root / "configs/kubeconfig")]
assert subprocess.check_output([*k, "config", "current-context"], text=True).strip() == "kind-sre-agent-dev"
network = json.loads(subprocess.check_output(["docker", "network", "inspect", "kind"]))[0]
gateway = next(c["Gateway"] for c in network["IPAM"]["Config"] if ipaddress.ip_address(c["Gateway"]).version == 4)
proxy = urlparse(os.environ["https_proxy"])
assert proxy.hostname == "127.0.0.1"
log = root / "artifacts/campaigns/diagnosis-20260921/environment-network-repair.jsonl"
script_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

def record(event, port):
    row = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, "port": port, "script_sha256": script_hash, "scope": "restore existing init proxy listener; no pod or deployment mutation"}
    with log.open("a") as f:
        f.write(json.dumps(row) + "\n")
    print(json.dumps(row), flush=True)

class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            with socket.create_connection((proxy.hostname, proxy.port), timeout=15) as upstream:
                while True:
                    ready, _, _ = select.select([self.request, upstream], [], [], 60)
                    if not ready:
                        return
                    for source in ready:
                        data = source.recv(65536)
                        if not data:
                            return
                        (upstream if source is self.request else self.request).sendall(data)
        except OSError:
            return

class Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

servers = {}
deadline = time.monotonic() + 21600
try:
    while time.monotonic() < deadline:
        wanted = set()
        try:
            with urlopen("http://127.0.0.1:18000/status", timeout=3) as response:
                stage = json.load(response)["stage"]
            if stage == "setup":
                result = subprocess.run([*k, "get", "deployment", "media-frontend", "nginx-thrift", "-n", "social-network", "-o", "json"], capture_output=True, timeout=20)
                if result.returncode == 0:
                    for d in json.loads(result.stdout)["items"]:
                        s = d.get("status", {})
                        if s.get("replicas") == 1 and s.get("updatedReplicas") == 1 and s.get("availableReplicas") == 1 and not s.get("unavailableReplicas", 0):
                            continue
                        for c in d["spec"]["template"]["spec"].get("initContainers", []):
                            for e in c.get("env", []):
                                if e["name"] == "HTTPS_PROXY":
                                    address = urlparse(e["value"])
                                    if address.hostname == gateway and address.port:
                                        wanted.add(address.port)
        except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
            pass
        for port in wanted - servers.keys():
            try:
                server = Server((gateway, port), Handler)
            except OSError:
                continue  # The original setup helper still owns this listener.
            servers[port] = server
            threading.Thread(target=server.serve_forever, daemon=True).start()
            record("listener_restored", port)
        for port in set(servers) - wanted:
            server = servers.pop(port)
            server.shutdown()
            server.server_close()
            record("listener_closed", port)
        time.sleep(3)
finally:
    for port, server in servers.items():
        server.shutdown()
        server.server_close()
        record("listener_closed", port)
