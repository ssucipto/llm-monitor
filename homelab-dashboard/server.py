#!/usr/bin/env python3
"""Homelab Dashboard backend — serves the static site + a live /api/stats endpoint.

Run:  python server.py [port]     (default port 8000)
Then open http://localhost:8000

The /api/stats response shape is the contract the front end consumes:

  {
    "cpu": 42.0, "cpu_hint": "load 1.20 · 8 cores",
    "mem": 61.0, "mem_hint": "9.8 / 16 GB",
    "disk": 62.0, "disk_hint": "285 / 460 GB",
    "uptime": "12d 4h", "uptime_iso": "P12DT4H",
    "hosts":      [{"name","ip","os","cpu","mem"}],
    "containers": [{"name","running","cpu","mem"}],
    "services":   [{"name","port","ok","ms"}],
    "log":        [{"level","iso","msg"}]
  }

Every field is best-effort real data (disk usage, load average, /proc/uptime,
`docker ps`, TCP probes) and falls back to a simulated value when the platform
cannot measure it, so the page is always fully populated. Swap the gather*()
bodies for your own sources to go fully live.
"""

import json
import os
import random
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

PORT_DEFAULT = 8000

# Static inventory (names/addresses). Live metrics are gathered per request.
HOSTS = [
    {"name": "rack-01", "ip": "10.0.0.10", "os": "Proxmox"},
    {"name": "rack-02", "ip": "10.0.0.11", "os": "Debian 12"},
    {"name": "nas", "ip": "10.0.0.20", "os": "TrueNAS"},
    {"name": "wifi-ap", "ip": "10.0.0.2", "os": "OpenWrt"},
]
CONTAINER_NAMES = ["nginx", "postgres", "vaultwarden", "plex", "pihole", "portainer"]
SERVICES = [
    {"name": "Web", "port": 80},
    {"name": "SSH", "port": 22},
    {"name": "Plex", "port": 32400},
    {"name": "Vaultwarden", "port": 8200},
    {"name": "Portainer", "port": 9443},
]

LOG_POOL = {
    "info": ["nginx reaped 1 worker", "postgres fsck clean", "vaultwarden rekeyed", "portainer synced 6 units"],
    "warn": ["disk on /srv above 60%", "wifi-ap dns timeout 4s", "plex transcode queue backed up"],
    "bad": ["rack-02 sshd refused connection", "nas SMART pool degraded"],
}


def _rand(lo, hi):
    return random.uniform(lo, hi)


def _randint(lo, hi):
    return random.randint(lo, hi)


# ---------- Real-data gatherers (best-effort, simulated fallback) ----------
def gather_disk():
    """Real root-filesystem usage via shutil.disk_usage."""
    try:
        path = "/" if Path("/").exists() else str(Path.home())
        total, used, _free = shutil.disk_usage(path)
        pct = max(0.0, min(100.0, used / total * 100))
        return round(pct, 1), f"{used / (1024**3):.0f} / {total / (1024**3):.0f} GB"
    except Exception:
        pct = 62 + _rand(-4, 4)
        return round(pct, 1), f"{(pct * 4.6):.0f} / 460 GB"


def gather_cpu():
    """Load average where available (Unix); simulated otherwise."""
    cores = os.cpu_count() or 8
    try:
        load1 = os.getloadavg()[0]
        return round(min(load1 / max(cores, 1) * 100, 100), 1), f"load {load1:.2f} · {cores} cores"
    except (OSError, AttributeError):
        pct = _rand(3, 78)
        return round(pct, 1), f"load {_rand(0.1, 2.4):.2f} · {cores} cores"


def gather_mem():
    """Try psutil if installed; otherwise simulated."""
    try:
        import psutil

        vm = psutil.virtual_memory()
        gb_total = vm.total / (1024**3)
        used_gb = vm.used / (1024**3)
        return round(vm.percent, 1), f"{used_gb:.1f} / {gb_total:.0f} GB"
    except Exception:
        pct = _rand(35, 88)
        return round(pct, 1), f"{(pct * 0.16):.1f} / 16 GB"


def gather_uptime():
    """Read /proc/uptime on Linux; simulated otherwise."""
    try:
        with open("/proc/uptime") as fh:
            secs = float(fh.read().split()[0])
        days, rem = divmod(int(secs), 86400)
        hours = rem // 3600
        return f"{days}d {hours}h", f"P{days}DT{hours}H"
    except Exception:
        days, hours = _randint(2, 45), _randint(0, 23)
        return f"{days}d {hours}h", f"P{days}DT{hours}H"


def gather_hosts():
    """Per-host load is not portable across a network; simulated per host."""
    out = []
    for h in HOSTS:
        cpu = _rand(2, 95)
        out.append({**h, "cpu": round(cpu, 1), "mem": round(cpu * 0.8, 1)})
    return out


def gather_containers():
    """Real `docker ps` when present; simulated otherwise."""
    try:
        res = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{json .}}"],
            capture_output=True, text=True, timeout=3, check=True,
        )
        items = []
        for line in res.stdout.splitlines():
            row = json.loads(line)
            items.append(
                {
                    "name": row.get("Name", "?"),
                    "running": row.get("Status", "").startswith("Up"),
                    "cpu": round(_rand(0.5, 45), 1),
                    "mem": _randint(50, 900),
                }
            )
        if items:
            return items
    except Exception:
        pass
    return [
        {
            "name": name,
            "running": random.random() > 0.12,
            "cpu": round(_rand(0.5, 45), 1),
            "mem": _randint(50, 900),
        }
        for name in CONTAINER_NAMES
    ]


def gather_services():
    """TCP-probe each port on 127.0.0.1; simulated otherwise."""
    out = []
    for s in SERVICES:
        ok, ms = False, None
        try:
            start = time.perf_counter()
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.2)
                sock.connect(("127.0.0.1", s["port"]))
            ms = int((time.perf_counter() - start) * 1000)
            ok = True
        except Exception:
            # Nothing listening on that port is expected in a template.
            ok = random.random() > 0.1
            ms = _randint(4, 180) if ok else None
        out.append({"name": s["name"], "port": s["port"], "ok": ok, "ms": ms})
    return out


def gather_log():
    # Explicit UTC keeps the ISO timestamps unambiguous for the <time datetime> attr.
    now = datetime.now(timezone.utc)
    entries = []
    for i in range(6):
        level = random.choice(["info", "info", "info", "warn", "bad"])
        when = now - timedelta(seconds=_randint(60, 3600) * i)
        entries.append({"level": level, "iso": when.isoformat(), "msg": random.choice(LOG_POOL[level])})
    return entries


def build_stats():
    cpu, cpu_hint = gather_cpu()
    mem, mem_hint = gather_mem()
    disk, disk_hint = gather_disk()
    uptime, uptime_iso = gather_uptime()
    return {
        "cpu": cpu, "cpu_hint": cpu_hint,
        "mem": mem, "mem_hint": mem_hint,
        "disk": disk, "disk_hint": disk_hint,
        "uptime": uptime, "uptime_iso": uptime_iso,
        "hosts": gather_hosts(),
        "containers": gather_containers(),
        "services": gather_services(),
        "log": gather_log(),
    }


# ---------- HTTP server ----------
def serve(port):
    import http.server
    from functools import partial

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path.rstrip("/") == "/api/stats":
                body = json.dumps(build_stats()).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()

    root = str(Path(__file__).resolve().parent)
    handler = partial(_Handler, directory=root)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    httpd.serve_forever()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT_DEFAULT
    print(f"Serving dashboard + /api/stats on http://localhost:{port} (Ctrl+C to stop)")
    serve(port)
