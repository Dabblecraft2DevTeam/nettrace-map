# OPNsense NetFlow Export Configuration Guide

This guide walks you through configuring OPNsense to export NetFlow data to NetTrace Map.

## Prerequisites

- OPNsense firewall (any recent version)
- NetTrace Map backend running and accessible from OPNsense
- The NetTrace Map server's IP address and port (default: `2055` UDP)

---

## Step 1: Enable NetFlow in OPNsense

OPNsense includes a NetFlow exporter via the `netflow` module. You need to enable it from the CLI or the web interface.

### Option A: Via Web Interface

1. Log into your OPNsense web interface
2. Navigate to **System → Configuration → Validators** (or **Interfaces → Diagnostics → NetFlow** depending on version)
3. Look for **NetFlow** or **Diagnostics → NetFlow** in the menu

> **Note:** The exact path depends on your OPNsense version. In some versions, NetFlow is under **Reporting → NetFlow**.

### Option B: Via SSH/CLI

For more control, use the CLI approach with `softflowd` or OPNsense's built-in netflow daemon:

```bash
# SSH into your OPNsense firewall
ssh root@your.opnsense.ip

# Check if netflow/softflowd is available
pkg info | grep -i flow
```

---

## Step 2: Install softflowd (if not built-in)

If OPNsense doesn't have a built-in NetFlow exporter accessible, install `softflowd`:

```bash
# On OPNsense (FreeBSD pkg)
pkg install softflowd
```

Or use OPNsense's plugin system:

```bash
# Check available plugins
opnsense-code netflow

# Or via the web interface:
# System → Firmware → Plugins → search "netflow"
```

---

## Step 3: Configure NetFlow Export

### Using softflowd

Configure softflowd to capture traffic on your WAN/LAN interfaces and export NetFlow v5 or v9 to NetTrace Map:

```bash
# Example: Capture on WAN interface (em0) and export to NetTrace Map
softflowd -i em0 -n 10.0.0.100:2055 -v 9

# For multiple interfaces, run separate instances:
softflowd -i em0 -n 10.0.0.100:2055 -v 9
softflowd -i igb0 -n 10.0.0.100:2055 -v 9
```

**Parameters:**
- `-i em0` — Interface to monitor (use `ifconfig` to list interfaces)
- `-n 10.0.0.100:2055` — NetTrace Map server IP and port
- `-v 9` — NetFlow version (9 is recommended for IPFIX support)
- `-t maxlife=60` — Maximum flow lifetime in seconds (optional)

### Using OPNsense Built-in NetFlow (if available)

If your OPNsense version has built-in NetFlow support:

1. Navigate to **Reporting → NetFlow** (or similar)
2. Enable NetFlow collection
3. Set the **Export Target** to your NetTrace Map server IP
4. Set the **Export Port** to `2055`
5. Set the **NetFlow Version** to `v9` (recommended) or `v5`
6. Select the interfaces to monitor (WAN and LAN)
7. Save and apply

---

## Step 4: Create a Persistent Service

To ensure NetFlow export survives reboots, create a startup script.

### Method 1: OPNsense Service (rc.conf)

```bash
# Edit /etc/rc.conf
vi /etc/rc.conf

# Add softflowd entries:
softflowd_enable="YES"
softflowd_interfaces="em0 igb0"
softflowd_em0="-n 10.0.0.100:2055 -v 9"
softflowd_igb0="-n 10.0.0.100:2055 -v 9"
```

Then start the service:

```bash
service softflowd start
```

### Method 2: Cron Job via OPNsense UI

1. Go to **System → Settings → Cron**
2. Add a cron job that runs `@reboot`:
   ```
   @reboot root /usr/local/bin/softflowd -i em0 -n 10.0.0.100:2055 -v 9 -d
   ```
3. Save and apply

### Method 3: OPNsense Plugin (recommended for production)

If OPNsense has a NetFlow plugin available:

1. Go to **System → Firmware → Plugins**
2. Search for `os-netflow` or similar
3. Install the plugin
4. Configure via **Reporting → NetFlow** in the web UI

---

## Step 5: Verify NetFlow Data is Flowing

### On the NetTrace Map Server

```bash
# Check if UDP 2055 is receiving data
tcpdump -i any udp port 2055 -nn

# You should see packets like:
# 22:01:34.123456 IP your.opnsense.ip.12345 > your.server.ip.2055: UDP, length 150
```

### In NetTrace Map

1. Open the NetTrace Map web interface (`http://your-server:8000`)
2. Disable demo mode: `export NETTRACE_DEMO=0` and restart the server
3. You should see animated packets appearing on the map

### Check Backend Logs

```bash
# The backend logs will show:
# [nettrace.server] INFO: NetFlow collector listening on 0.0.0.0:2055 (UDP)
# [nettrace.server] INFO: WebSocket client connected
```

---

## Step 6: Firewall Rules

Ensure your OPNsense firewall allows outbound NetFlow traffic:

1. Go to **Firewall → Rules → LAN** (or whichever interface the NetTrace Map server is on)
2. Add a rule:
   - **Action:** Pass
   - **Interface:** LAN
   - **Protocol:** UDP
   - **Source:** OPNsense interface IP
   - **Destination:** NetTrace Map server IP
   - **Destination Port:** 2055
3. Save and apply

---

## Step 7: Tuning

### Flow Timeout

Adjust the active/inactive flow timeouts for better granularity:

```bash
# Shorter timeouts = more frequent flow exports
softflowd -i em0 -n 10.0.0.100:2055 -v 9 -t maxlife=30 -t maxidle=15
```

- `maxlife=30` — Export active flows every 30 seconds
- `maxidle=15` — Export inactive flows after 15 seconds of no traffic

### Sampling Rate (for high-traffic networks)

If your network has very high traffic, consider sampling:

```bash
softflowd -i em0 -n 10.0.0.100:2055 -v 9 -s 100
```

- `-s 100` — Sample 1 in every 100 packets

### Multiple Interfaces

To capture on both WAN and LAN:

```bash
# Create separate softflowd instances for each interface
softflowd -i em0 -n 10.0.0.100:2055 -v 9 -p /var/run/softflowd_wan.pid
softflowd -i igb0 -n 10.0.0.100:2055 -v 9 -p /var/run/softflowd_lan.pid
```

---

## Troubleshooting

### No packets arriving at NetTrace Map

1. **Check softflowd is running:**
   ```bash
   ps aux | grep softflowd
   ```

2. **Check network connectivity:**
   ```bash
   # From OPNsense, test connectivity to NetTrace Map
   nc -u -z 10.0.0.100 2055
   ```

3. **Check firewall rules** on both OPNsense and the NetTrace Map server:
   ```bash
   # On the NetTrace Map server
   sudo ufw allow 2055/udp
   # or
   sudo iptables -A INPUT -p udp --dport 2055 -j ACCEPT
   ```

4. **Verify interface names:**
   ```bash
   ifconfig  # List all interfaces on OPNsense
   ```

### NetFlow v9 templates not parsing

The built-in NetFlow v9 parser handles common templates. If you see parse errors:

1. Install the optional `netflow-parser` library:
   ```bash
   pip install netflow-parser
   ```

2. Or switch to NetFlow v5 (simpler, no templates):
   ```bash
   softflowd -i em0 -n 10.0.0.100:2055 -v 5
   ```

### High CPU usage

- Use sampling (`-s 100` or higher)
- Monitor fewer interfaces
- Increase flow timeouts to reduce export frequency

---

## Alternative: Using pmacct for Advanced Collection

For more advanced NetFlow collection, consider [pmacct](https://github.com/pmacct/pmacct):

```bash
# Install pmacct on OPNsense or a dedicated collector
pkg install pmacct

# Configure /usr/local/etc/pmacctd.conf
# See pmacct documentation for NetFlow export configuration
```

pmacct supports NetFlow v5/v9, sFlow, and IPFIX with more advanced filtering and aggregation options.

---

## Quick Reference

| Setting | Value |
|---|---|
| NetTrace Map default port | `2055` UDP |
| Recommended NetFlow version | v9 |
| Default demo mode | Enabled (simulated flows) |
| Config file | `backend/config.py` |
| Environment variable for port | `NETTRACE_NF_PORT=2055` |
| Environment variable for demo | `NETTRACE_DEMO=0` (disable) |