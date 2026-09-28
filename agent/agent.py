#!/usr/bin/env python3
"""
NetTrace Map — Monitoring Agent
Single-file, stdlib-only system metrics collector for NetTrace Map.

Collects: hostname, IPs, CPU, RAM, disk, network I/O, uptime, load,
          temperature, running services (port checks).
Reports via HTTP POST to the NetTrace backend.

Usage:
  python3 agent.py [--server URL] [--interval SECONDS] [--name NAME] [--cluster CLUSTER]

Config file (optional): /etc/nettrace-agent.conf  (INI format, see below)
  [nettrace]
  server = http://localhost:8000
  interval = 5
  instance_name = my-host
  cluster = OVH BHS

Requires: Python 3.8+  (stdlib only)
Optional: psutil (used if available for better accuracy)
"""

import argparse
import configparser
import json
import os
import socket
import struct
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_VERSION = "1.0.0"
DEFAULT_SERVER = "http://localhost:8000"
DEFAULT_INTERVAL = 5
DEFAULT_CONFIG_PATH = "/etc/nettrace-agent.conf"

# Service ports to check (label -> port)
SERVICE_PORTS = {
    "ssh": 22,
    "mysql": 3306,
    "redis": 6379,
    "minecraft": 25565,
}

# ---------------------------------------------------------------------------
# Optional psutil import
# ---------------------------------------------------------------------------

try:
    import psutil
    HAVE_PSUTIL = True
except ImportError:
    HAVE_PSUTIL = False


# ---------------------------------------------------------------------------
# Metrics collectors
# ---------------------------------------------------------------------------

def get_hostname():
    """Get system hostname."""
    return socket.gethostname()


def get_ip_addresses():
    """Get all non-loopback IPv4 addresses on all interfaces."""
    ips = {}
    try:
        hostname = socket.gethostname()
        # Try getaddrinfo for primary IP
        try:
            info = socket.getaddrinfo(hostname, None, socket.AF_INET)
            for item in info:
                ip = item[4][0]
                if ip != "127.0.0.1" and ip not in ips.values():
                    ips[socket.if_nameindex()[0][1] if hasattr(socket, 'if_nameindex') else "primary"] = ip
        except Exception:
            pass
    except Exception:
        pass

    # Fallback: connect a UDP socket to determine primary IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        primary_ip = s.getsockname()[0]
        s.close()
        if primary_ip not in ips.values():
            ips["primary"] = primary_ip
    except Exception:
        pass

    # Try to enumerate interfaces from /proc/net/fib_trie or ifconfig
    try:
        import subprocess
        result = subprocess.run(["ip", "-4", "-o", "addr"], capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                parts = line.split()
                if len(parts) >= 4:
                    iface = parts[1]
                    ip = parts[3].split("/")[0]
                    if ip != "127.0.0.1":
                        ips[iface] = ip
    except Exception:
        pass

    return ips


# --- CPU metrics ---

_prev_cpu_times = None

def get_cpu_usage():
    """Get CPU usage percentage (0-100)."""
    global _prev_cpu_times

    if HAVE_PSUTIL:
        return psutil.cpu_percent(interval=0.5)

    # Fallback: parse /proc/stat
    try:
        with open("/proc/stat", "r") as f:
            line = f.readline()
        parts = line.split()
        # user, nice, system, idle, iowait, irq, softirq, steal
        times = [float(x) for x in parts[1:9] if x]
        if len(times) < 4:
            times = times + [0.0] * (4 - len(times))
        idle = times[3]
        total = sum(times[:8] if len(times) >= 8 else times)

        if _prev_cpu_times is not None:
            prev_idle = _prev_cpu_times[3]
            prev_total = sum(_prev_cpu_times[:8] if len(_prev_cpu_times) >= 8 else _prev_cpu_times)
            delta_total = total - prev_total
            delta_idle = idle - prev_idle
            if delta_total > 0:
                usage = (1.0 - delta_idle / delta_total) * 100.0
                _prev_cpu_times = times[:8]
                return round(max(0.0, min(100.0, usage)), 1)

        _prev_cpu_times = times[:8]
        # Need two readings — sleep briefly and retry
        time.sleep(0.5)
        with open("/proc/stat", "r") as f:
            line = f.readline()
        parts = line.split()
        times2 = [float(x) for x in parts[1:9] if x]
        idle2 = times2[3]
        total2 = sum(times2[:8] if len(times2) >= 8 else times2)
        delta_total = total2 - total
        delta_idle = idle2 - idle
        if delta_total > 0:
            usage = (1.0 - delta_idle / delta_total) * 100.0
            _prev_cpu_times = times2[:8]
            return round(max(0.0, min(100.0, usage)), 1)
        return 0.0
    except Exception:
        return 0.0


def get_cpu_cores():
    """Get number of CPU cores."""
    if HAVE_PSUTIL:
        return psutil.cpu_count(logical=True) or 1
    try:
        return os.cpu_count() or 1
    except Exception:
        return 1


# --- Memory metrics ---

def get_memory():
    """Get memory usage: used, total, percent."""
    if HAVE_PSUTIL:
        mem = psutil.virtual_memory()
        return {
            "total": mem.total,
            "used": mem.used,
            "available": mem.available,
            "percent": round(mem.percent, 1),
        }

    # Fallback: parse /proc/meminfo
    try:
        info = {}
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    info[parts[0].rstrip(":")] = int(parts[1]) * 1024  # kB to bytes
        total = info.get("MemTotal", 0)
        available = info.get("MemAvailable", info.get("MemFree", 0))
        used = total - available
        percent = (used / total * 100.0) if total > 0 else 0.0
        return {
            "total": total,
            "used": used,
            "available": available,
            "percent": round(percent, 1),
        }
    except Exception:
        return {"total": 0, "used": 0, "available": 0, "percent": 0.0}


# --- Disk metrics ---

def get_disk():
    """Get disk usage for root partition (/)."""
    if HAVE_PSUTIL:
        try:
            usage = psutil.disk_usage("/")
            return {
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": round(usage.percent, 1),
            }
        except Exception:
            pass

    # Fallback: os.statvfs
    try:
        stat = os.statvfs("/")
        total = stat.f_blocks * stat.f_frsize
        free = stat.f_bavail * stat.f_frsize
        used = total - free
        percent = (used / total * 100.0) if total > 0 else 0.0
        return {
            "total": total,
            "used": used,
            "free": free,
            "percent": round(percent, 1),
        }
    except Exception:
        return {"total": 0, "used": 0, "free": 0, "percent": 0.0}


# --- Network metrics ---

_prev_net_stats = None

def get_network_io():
    """Get network I/O bytes in/out per second (rate since last call)."""
    global _prev_net_stats

    if HAVE_PSUTIL:
        counters = psutil.net_io_counters()
        bytes_in = counters.bytes_recv
        bytes_out = counters.bytes_sent
    else:
        # Fallback: parse /proc/net/dev
        bytes_in = 0
        bytes_out = 0
        try:
            with open("/proc/net/dev", "r") as f:
                lines = f.readlines()[2:]  # skip header lines
                for line in lines:
                    parts = line.split()
                    iface = parts[0].rstrip(":")
                    if iface == "lo":
                        continue
                    bytes_in += int(parts[1])
                    bytes_out += int(parts[9])
        except Exception:
            pass

    now = time.time()
    if _prev_net_stats is not None:
        prev_in, prev_out, prev_time = _prev_net_stats
        dt = now - prev_time
        if dt > 0:
            rate_in = (bytes_in - prev_in) / dt
            rate_out = (bytes_out - prev_out) / dt
        else:
            rate_in = 0
            rate_out = 0
        _prev_net_stats = (bytes_in, bytes_out, now)
        return {
            "bytes_in_rate": round(max(0, rate_in)),
            "bytes_out_rate": round(max(0, rate_out)),
            "total_in": bytes_in,
            "total_out": bytes_out,
        }

    _prev_net_stats = (bytes_in, bytes_out, now)
    return {
        "bytes_in_rate": 0,
        "bytes_out_rate": 0,
        "total_in": bytes_in,
        "total_out": bytes_out,
    }


# --- Uptime ---

def get_uptime():
    """Get system uptime in seconds."""
    if HAVE_PSUTIL:
        try:
            import psutil as _p
            # psutil doesn't have uptime directly; use boot_time
            boot = _p.boot_time()
            return int(time.time() - boot)
        except Exception:
            pass

    try:
        with open("/proc/uptime", "r") as f:
            return int(float(f.readline().split()[0]))
    except Exception:
        return 0


# --- Load average ---

def get_load_average():
    """Get system load average (1, 5, 15 minute)."""
    try:
        load = os.getloadavg()
        return [round(load[0], 2), round(load[1], 2), round(load[2], 2)]
    except Exception:
        return [0.0, 0.0, 0.0]


# --- Temperature ---

def get_temperature():
    """Get CPU temperature if available from /sys/class/thermal/."""
    try:
        thermal_dir = "/sys/class/thermal/"
        temps = []
        for name in os.listdir(thermal_dir):
            if name.startswith("thermal_zone"):
                temp_file = os.path.join(thermal_dir, name, "temp")
                if os.path.isfile(temp_file):
                    with open(temp_file, "r") as f:
                        millideg = int(f.read().strip())
                        temps.append(millideg / 1000.0)
        if temps:
            return max(temps)
    except Exception:
        pass
    return None


# --- Service port checks ---

def check_services():
    """Check if specific service ports are listening locally."""
    services = {}
    for label, port in SERVICE_PORTS.items():
        services[label] = _check_port(port)
    return services


def _check_port(port):
    """Check if a TCP port is listening on localhost."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3)
        result = s.connect_ex(("127.0.0.1", port))
        s.close()
        return result == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Collect all metrics
# ---------------------------------------------------------------------------

def collect_metrics(instance_name, cluster):
    """Collect all system metrics into a single dict."""
    return {
        "agent_version": AGENT_VERSION,
        "instance_name": instance_name,
        "hostname": get_hostname(),
        "cluster": cluster,
        "ip_addresses": get_ip_addresses(),
        "cpu": {
            "usage_percent": get_cpu_usage(),
            "cores": get_cpu_cores(),
        },
        "memory": get_memory(),
        "disk": get_disk(),
        "network": get_network_io(),
        "uptime_seconds": get_uptime(),
        "load_average": get_load_average(),
        "temperature": get_temperature(),
        "services": check_services(),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "unix_timestamp": time.time(),
    }


# ---------------------------------------------------------------------------
# Report sender
# ---------------------------------------------------------------------------

def send_report(server_url, metrics):
    """POST metrics to the NetTrace backend."""
    url = server_url.rstrip("/") + "/api/agent-report"
    data = json.dumps(metrics).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200 or resp.status == 201
    except urllib.error.URLError as e:
        print(f"[nettrace-agent] Failed to send report to {url}: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[nettrace-agent] Error sending report: {e}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_config(config_path):
    """Load configuration from INI file if it exists."""
    config = {
        "server": DEFAULT_SERVER,
        "interval": DEFAULT_INTERVAL,
        "instance_name": None,
        "cluster": None,
    }
    if config_path and os.path.isfile(config_path):
        parser = configparser.ConfigParser()
        parser.read(config_path)
        if parser.has_section("nettrace"):
            if parser.has_option("nettrace", "server"):
                config["server"] = parser.get("nettrace", "server")
            if parser.has_option("nettrace", "interval"):
                config["interval"] = parser.getint("nettrace", "interval")
            if parser.has_option("nettrace", "instance_name"):
                config["instance_name"] = parser.get("nettrace", "instance_name")
            if parser.has_option("nettrace", "cluster"):
                config["cluster"] = parser.get("nettrace", "cluster")
    return config


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="NetTrace Map Monitoring Agent")
    parser.add_argument("--server", "-s", help="NetTrace backend URL (e.g. http://localhost:8000)")
    parser.add_argument("--interval", "-i", type=int, help="Report interval in seconds (default: 5)")
    parser.add_argument("--name", "-n", help="Instance name (default: hostname)")
    parser.add_argument("--cluster", "-c", help="Cluster name this machine belongs to")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Config file path")
    parser.add_argument("--once", action="store_true", help="Collect and send one report, then exit")
    parser.add_argument("--dry-run", action="store_true", help="Collect metrics and print, don't send")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    # Load config file, then override with CLI args
    cfg = load_config(args.config)
    server_url = args.server or cfg["server"]
    interval = args.interval or cfg["interval"]
    instance_name = args.name or cfg["instance_name"] or get_hostname()
    cluster = args.cluster or cfg["cluster"] or "unknown"

    print(f"[nettrace-agent] v{AGENT_VERSION} starting")
    print(f"  Server:   {server_url}")
    print(f"  Interval: {interval}s")
    print(f"  Name:     {instance_name}")
    print(f"  Cluster:  {cluster}")
    print(f"  psutil:   {'yes' if HAVE_PSUTIL else 'no (using /proc fallback)'}")

    # Warm up network/CPU rate counters
    _ = get_network_io()
    _ = get_cpu_usage()

    if args.once or args.dry_run:
        metrics = collect_metrics(instance_name, cluster)
        if args.dry_run:
            print(json.dumps(metrics, indent=2))
            return
        success = send_report(server_url, metrics)
        print(f"Report sent: {'OK' if success else 'FAILED'}")
        sys.exit(0 if success else 1)

    # Main loop
    consecutive_failures = 0
    max_backoff = 60

    while True:
        try:
            metrics = collect_metrics(instance_name, cluster)

            if args.verbose:
                print(f"[nettrace-agent] CPU={metrics['cpu']['usage_percent']}% "
                      f"RAM={metrics['memory']['percent']}% "
                      f"Disk={metrics['disk']['percent']}% "
                      f"Net={metrics['network']['bytes_in_rate']}/{metrics['network']['bytes_out_rate']} B/s")

            success = send_report(server_url, metrics)
            if success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                backoff = min(max_backoff, interval * (2 ** min(consecutive_failures - 1, 5)))
                print(f"[nettrace-agent] Backend unreachable (attempt {consecutive_failures}), "
                      f"retrying in {backoff}s", file=sys.stderr)
                time.sleep(backoff)
                continue

        except KeyboardInterrupt:
            print("\n[nettrace-agent] Shutting down (Ctrl-C)")
            break
        except Exception as e:
            print(f"[nettrace-agent] Unexpected error: {e}", file=sys.stderr)
            consecutive_failures += 1

        time.sleep(interval)


if __name__ == "__main__":
    main()