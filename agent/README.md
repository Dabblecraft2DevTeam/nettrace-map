# NetTrace Map — Monitoring Agent

A lightweight system metrics collector that reports to the NetTrace Map backend for live VM health visualization.

## Features

- **Single file, stdlib only** — no pip install required on target machines
- **Optional psutil** — uses psutil if available for better accuracy, falls back to `/proc` parsing
- **Systemd service** — auto-starts on boot, auto-restarts on crash
- **Auto-reconnect** — exponential backoff if backend is unreachable
- **Low overhead** — < 1% CPU, collects every 5 seconds by default

## Metrics Collected

| Metric | Description |
|--------|-------------|
| hostname | System hostname |
| ip_addresses | All non-loopback IPv4 addresses per interface |
| cpu.usage_percent | CPU utilization (0-100%) |
| cpu.cores | Number of CPU cores |
| memory.total/used/available/percent | RAM usage |
| disk.total/used/free/percent | Root partition (`/`) usage |
| network.bytes_in_rate / bytes_out_rate | Network I/O bytes/sec |
| network.total_in / total_out | Cumulative network I/O |
| uptime_seconds | System uptime |
| load_average | 1/5/15 minute load averages |
| temperature | CPU temperature (if `/sys/class/thermal/` available) |
| services | Port checks: SSH (22), MySQL (3306), Redis (6379), Minecraft (25565) |

## Quick Install

```bash
# On the target VM, as root:
sudo ./install.sh --server http://YOUR_NETTRACE_BACKEND:8000 --cluster "OVH BHS"
```

Options:
- `--server URL` — NetTrace backend URL (default: `http://localhost:8000`)
- `--interval N` — Report interval in seconds (default: 5)
- `--name NAME` — Instance name (default: hostname)
- `--cluster NAME` — Cluster name for map positioning (default: `unknown`)

## Manual Install (without install.sh)

```bash
# Copy agent
sudo mkdir -p /opt/nettrace-agent
sudo cp agent.py /opt/nettrace-agent/

# Create config
sudo tee /etc/nettrace-agent.conf << 'EOF'
[nettrace]
server = http://YOUR_BACKEND:8000
interval = 5
cluster = OVH BHS
EOF

# Create systemd service
sudo tee /etc/systemd/system/nettrace-agent.service << 'EOF'
[Unit]
Description=NetTrace Map Monitoring Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/nettrace-agent/agent.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=nettrace-agent

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now nettrace-agent
```

## Uninstall

```bash
sudo ./uninstall.sh
```

## Running Manually (for testing)

```bash
# One-shot report (collect + send once, then exit)
python3 agent.py --server http://localhost:8000 --cluster "Home" --once

# Dry run (collect + print, don't send)
python3 agent.py --dry-run

# Verbose continuous mode
python3 agent.py --server http://localhost:8000 --cluster "OVH BHS" -v

# Custom config file
python3 agent.py --config /path/to/custom.conf
```

## Logs

```bash
# Follow agent logs
journalctl -u nettrace-agent -f

# Last 50 lines
journalctl -u nettrace-agent -n 50

# Service status
systemctl status nettrace-agent
```

## Config File

Location: `/etc/nettrace-agent.conf`

```ini
[nettrace]
server = http://localhost:8000
interval = 5
instance_name = my-host       # optional, defaults to hostname
cluster = OVH BHS             # cluster name for map positioning
```

CLI arguments override config file values.

## Optional: psutil

For slightly better accuracy (especially CPU and network metrics), install psutil:

```bash
# Debian/Ubuntu
sudo apt install python3-psutil

# Or via pip
pip3 install psutil
```

The agent works fine without psutil — it falls back to parsing `/proc/stat`, `/proc/meminfo`, `/proc/net/dev`, and `/proc/uptime`.

## Architecture

```
┌─────────────────┐     HTTP POST      ┌─────────────────┐     WebSocket     ┌─────────────────┐
│  agent.py       │  ──────────────►   │  server.py      │  ──────────────►  │  app.js         │
│  (on each VM)   │  /api/agent-report │  (FastAPI)      │  VM health data   │  (frontend)     │
│                 │  every 5 seconds   │                 │                   │                 │
│  /proc parsing  │                    │  stores latest  │                   │  color-coded    │
│  port checks    │                    │  per agent       │                   │  VM nodes       │
│  hostname/IP    │                    │  broadcasts WS   │                   │  service icons  │
└─────────────────┘                    └─────────────────┘                   └─────────────────┘
```