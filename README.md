# NetTrace Map

**Network Traffic Visualization with Submarine Cable Overlay**

NetTrace Map is a web-based animated map that shows your network traffic flowing across the world in real time. It collects NetFlow data from OPNsense (or any NetFlow v5/v9 exporter), geolocates the endpoints, and renders animated packets traveling along great-circle arcs over a dark-themed world map with submarine cable overlays.

![NetTrace Map](https://img.shields.io/badge/status-alpha-orange) ![Python](https://img.shields.io/badge/python-3.11+-blue) ![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **Real-time NetFlow collection** — UDP listener for NetFlow v5 and v9 (IPFIX) packets
- **Animated packet visualization** — Dots travel along great-circle arcs between source and destination
- **Submarine cable overlay** — TeleGeography submarine cable routes displayed on the map
- **Pre-configured infrastructure** — Your OVH BHS/YYZ servers, home network, and internal VMs are pre-mapped
- **MaxMind GeoLite2 geolocation** — Unknown IPs are geolocated using the free GeoLite2-City database
- **Protocol color-coding** — BGP (purple), HTTP/HTTPS (green), SSH (orange), game traffic (blue), DNS (yellow)
- **BGP visualization** — Persistent peering lines and animated BGP UPDATE messages (configure once you have an ASN)
- **Live stats panel** — Total flows, bandwidth, protocol breakdown, top destinations
- **Dark theme** — Clean, professional dark UI using CartoDB Dark Matter tiles
- **Fully self-hosted** — No cloud dependencies, runs entirely on your infrastructure

## Architecture

```
┌──────────────┐     NetFlow v5/v9      ┌──────────────────┐     WebSocket      ┌────────────────┐
│   OPNsense   │ ──────────────────────► │  FastAPI Backend  │ ─────────────────► │  Web Frontend  │
│  (Router)    │     UDP :2055           │  (NetFlow + WS)   │     JSON flows     │  (Leaflet Map) │
└──────────────┘                         └──────────────────┘                    └────────────────┘
                                                │                                         │
                                         ┌───────┴───────┐                          ┌───────┴───────┐
                                         │  MaxMind      │                          │  Submarine    │
                                         │  GeoLite2     │                          │  Cable Data   │
                                         │  (local mmdb) │                          │  (GeoJSON)    │
                                         └───────────────┘                          └───────────────┘
```

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/Dabblecraft2DevTeam/nettrace-map.git
cd nettrace-map

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install backend dependencies
pip install -r backend/requirements.txt
```

### 2. Download GeoLite2 Database (Optional but recommended)

You need a free MaxMind license key:

1. Sign up at [maxmind.com](https://www.maxmind.com/en/geolite2/signup)
2. Get your license key from [your account](https://www.maxmind.com/en/accounts/current/license-key)
3. Run the download script:

```bash
export MAXMIND_LICENSE_KEY="your_key_here"
./download_geolite2.sh
```

The database will be saved to `data/GeoLite2-City.mmdb`.

> **Note:** Without the GeoLite2 database, only pre-configured IPs will be accurately geolocated. Unknown IPs will default to the OVH BHS area.

### 3. Start the Server

```bash
cd backend
python server.py
```

Or with uvicorn directly:

```bash
uvicorn backend.server:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Open the Map

Navigate to `http://localhost:8000` in your browser.

The server starts in **demo mode** by default, generating simulated traffic between your pre-configured machines so you can see the visualization immediately.

## Configuration

### Pre-configured Infrastructure

Edit `backend/config.py` to update your machine IPs and locations:

```python
MACHINES = [
    Machine(
        name="OVH BHS Datacenter",
        hostname="ovh-bhs",
        ip="YOUR.BHS.PUBLIC.IP",     # ← Replace with actual IP
        lat=45.31,
        lon=-73.87,
        role="XCP-NG Host / Factions / DB / Proxy / Router / XOCE",
        location="Beauharnois, Quebec, Canada",
    ),
    # ... add more machines
]
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `NETTRACE_NF_HOST` | `0.0.0.0` | NetFlow collector listen address |
| `NETTRACE_NF_PORT` | `2055` | NetFlow collector UDP port |
| `NETTRACE_DEMO` | `1` | Enable demo mode (simulated flows) — set to `0` for production |

### Disabling Demo Mode

Once you have NetFlow data flowing from OPNsense:

```bash
export NETTRACE_DEMO=0
python backend/server.py
```

## OPNsense NetFlow Configuration

See **[opnsense-netflow-guide.md](opnsense-netflow-guide.md)** for step-by-step instructions on configuring OPNsense to export NetFlow data to NetTrace Map.

## BGP Visualization

To enable BGP visualization:

1. Obtain an ASN from [ARIN](https://www.arin.net/)
2. Edit `backend/config.py`:
   ```python
   MY_ASN = 12345  # Your ARIN ASN
   MY_ASN_LAT = 45.31
   MY_ASN_LON = -73.87

   BGP_PEERS = [
       BGPPeer(asn=16276, name="OVH AS", lat=45.31, lon=-73.87, location="OVH BHS"),
       BGPPeer(asn=14061, name="DigitalOcean", lat=40.71, lon=-74.00, location="New York, USA"),
   ]
   ```
3. Restart the server — BGP peering lines will appear on the map

## File Structure

```
nettrace-map/
├── backend/
│   ├── server.py          # FastAPI + WebSocket + NetFlow collector
│   ├── geo.py             # MaxMind GeoLite2 geolocation
│   ├── config.py          # Pre-configured machines, IPs, BGP peers
│   └── requirements.txt   # Python dependencies
├── frontend/
│   ├── index.html         # Main page with Leaflet map
│   ├── style.css          # Dark theme styling
│   └── app.js             # WebSocket client, animation logic, map rendering
├── data/
│   ├── cables.geojson         # Submarine cable routes (TeleGeography data)
│   ├── landing_points.geojson # Submarine cable landing points
│   └── GeoLite2-City.mmdb     # MaxMind database (download separately)
├── download_geolite2.sh   # Script to fetch GeoLite2 database
├── opnsense-netflow-guide.md  # OPNsense configuration guide
├── README.md
└── .gitignore
```

## Data Sources

- **Submarine cables**: [TeleGeography Submarine Cable Map](https://www.submarinecablemap.com/) data via [lintaojlu/submarine_cable_information](https://github.com/lintaojlu/submarine_cable_information) and [shimizu's gist](https://gist.github.com/shimizu/6b7123b893fca8440e70216cddfcfe52)
- **Geolocation**: [MaxMind GeoLite2](https://dev.maxmind.com/geoip/geolite2-free-geolocation-data) (free, requires license key)
- **Map tiles**: [CartoDB Dark Matter](https://carto.com/basemaps/) (free, OSM-based)

## Tech Stack

| Component | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI, uvicorn |
| NetFlow | Built-in v5/v9 parser (NetFlow UDP collector) |
| Geolocation | MaxMind GeoLite2 + geoip2 Python library |
| Frontend | HTML5, vanilla JavaScript, Leaflet.js |
| Map tiles | CartoDB Dark Matter (OSM) |
| Real-time | WebSocket (FastAPI native) |

## Troubleshooting

### No flows appearing
- Check that demo mode is enabled (`NETTRACE_DEMO=1`)
- Check WebSocket connection in browser console
- Verify the backend is running and accessible

### GeoLite2 not loading
- Run `./download_geolite2.sh` with a valid license key
- Check that `data/GeoLite2-City.mmdb` exists
- Verify `geoip2` is installed: `pip install geoip2`

### NetFlow packets not received
- Verify OPNsense NetFlow export points to this server's IP and port 2055
- Check firewall rules allow UDP 2055 inbound
- Test with `nc -ul 2055` on the server to verify packets arrive

## License

MIT — See LICENSE file for details.

## Acknowledgements

- [TeleGeography](https://www.submarinecablemap.com/) for submarine cable data
- [MaxMind](https://www.maxmind.com/) for GeoLite2 geolocation database
- [CartoDB](https://carto.com/) for dark theme map tiles
- [Leaflet](https://leafletjs.com/) for the mapping library