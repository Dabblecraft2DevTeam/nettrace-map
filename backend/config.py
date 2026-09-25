"""
NetTrace Map — Configuration
Pre-configured infrastructure endpoints for geolocation.
XCP-NG VM inventory fetched from XO API at http://172.1.0.5
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Machine:
    """A known machine or network endpoint."""
    name: str
    hostname: str
    ip: str          # External/public IP or internal IP
    lat: float
    lon: float
    role: str
    location: str
    internal: bool = False           # True for private-space IPs
    external_ip: Optional[str] = None  # Maps to a public IP / datacenter
    cluster: Optional[str] = None    # Cluster name for grouping (e.g. "OVH BHS")


# ---------------------------------------------------------------------------
# Pre-configured infrastructure — XCP-NG VMs from XO API
# ---------------------------------------------------------------------------

MACHINES: list[Machine] = [
    # === OVH BHS Datacenter — XCP-NG Host (all VMs) ===
    Machine(
        name="GC02-Router",
        hostname="router",
        ip="172.1.0.1",
        lat=45.31,
        lon=-73.87,
        role="OPNsense Router / Edge Firewall / BGP",
        location="OVH BHS (internal)",
        internal=True,
        external_ip="51.222.28.245",
        cluster="OVH BHS",
    ),
    Machine(
        name="GC02-Proxy",
        hostname="proxy",
        ip="172.1.0.100",
        lat=45.31,
        lon=-73.87,
        role="Reverse Proxy",
        location="OVH BHS (internal)",
        internal=True,
        external_ip="51.222.28.245",
        cluster="OVH BHS",
    ),
    Machine(
        name="XOCE",
        hostname="xoce",
        ip="172.1.0.5",
        lat=45.31,
        lon=-73.87,
        role="XCP-NG Orchestra (VM Management)",
        location="OVH BHS (internal)",
        internal=True,
        external_ip="51.222.28.245",
        cluster="OVH BHS",
    ),
    Machine(
        name="GC02-Hub",
        hostname="hub",
        ip="172.1.0.101",
        lat=45.31,
        lon=-73.87,
        role="Minecraft Hub Server (6GB)",
        location="OVH BHS (internal)",
        internal=True,
        external_ip="51.222.28.245",
        cluster="OVH BHS",
    ),
    Machine(
        name="GC02-Combat-1",
        hostname="combat1",
        ip="172.1.0.104",
        lat=45.31,
        lon=-73.87,
        role="Minecraft Combat VM (15GB) — Factions",
        location="OVH BHS (internal)",
        internal=True,
        external_ip="51.222.28.245",
        cluster="OVH BHS",
    ),
    Machine(
        name="GC02-NorthSeas",
        hostname="northseas",
        ip="172.1.0.103",
        lat=45.31,
        lon=-73.87,
        role="Minecraft NorthSeas (7GB)",
        location="OVH BHS (internal)",
        internal=True,
        external_ip="51.222.28.245",
        cluster="OVH BHS",
    ),
    Machine(
        name="GC02-SeaTrials",
        hostname="seatrials",
        ip="172.1.0.102",
        lat=45.31,
        lon=-73.87,
        role="Minecraft SeaTrials (5GB)",
        location="OVH BHS (internal)",
        internal=True,
        external_ip="51.222.28.245",
        cluster="OVH BHS",
    ),
    Machine(
        name="GC02-DB",
        hostname="db-vm",
        ip="172.1.0.105",
        lat=45.31,
        lon=-73.87,
        role="Database VM — MariaDB/Redis",
        location="OVH BHS (internal)",
        internal=True,
        external_ip="51.222.28.245",
        cluster="OVH BHS",
    ),

    # === OVH YYZ Datacenter ===
    Machine(
        name="OVH YYZ S3 Storage",
        hostname="ovh-yyz",
        ip="192.99.0.2",          # Placeholder — replace with YYZ public IP
        lat=43.65,
        lon=-79.38,
        role="S3 Object Storage",
        location="Toronto, Ontario, Canada",
        cluster="OVH YYZ",
    ),

    # === DabbleBot VPS (separate OVH BHS instance) ===
    Machine(
        name="DabbleBot VPS",
        hostname="dabblebot",
        ip="51.222.28.245",
        lat=45.31,
        lon=-73.87,
        role="DabbleBot Discord Bot",
        location="Beauharnois, Quebec, Canada (OVH BHS)",
        cluster="OVH BHS",
    ),

    # === Home Network ===
    Machine(
        name="Home Network",
        hostname="home",
        ip="10.0.0.81",
        lat=45.40,
        lon=-73.90,
        role="Hermes Machine / Omada Network / TBE550E WiFi7",
        location="Montreal area, Quebec, Canada",
        internal=True,
        cluster="Home",
    ),
]

# Quick lookup: IP -> Machine
IP_MAP: dict[str, Machine] = {m.ip: m for m in MACHINES}

# Also map hostname -> Machine for convenience
HOSTNAME_MAP: dict[str, Machine] = {m.hostname: m for m in MACHINES}

# Cluster definitions for the virtual server box visualization
CLUSTERS = {
    "OVH BHS": {
        "name": "OVH BHS Datacenter",
        "location": "Beauharnois, Quebec, Canada",
        "lat": 45.31,
        "lon": -73.87,
        "edge_ip": "51.222.28.245",  # Router/OPNsense public IP
        "edge_name": "GC02-Router (OPNsense)",
        "vms": [
            {"name": "GC02-Router", "ip": "172.1.0.1", "role": "OPNsense Edge", "ram": "1GB"},
            {"name": "GC02-Proxy", "ip": "172.1.0.100", "role": "Reverse Proxy", "ram": "1GB"},
            {"name": "XOCE", "ip": "172.1.0.5", "role": "XO Management", "ram": "4GB"},
            {"name": "GC02-Hub", "ip": "172.1.0.101", "role": "MC Hub", "ram": "6GB"},
            {"name": "GC02-Combat-1", "ip": "172.1.0.104", "role": "MC Factions", "ram": "15GB"},
            {"name": "GC02-NorthSeas", "ip": "172.1.0.103", "role": "MC NorthSeas", "ram": "7GB"},
            {"name": "GC02-SeaTrials", "ip": "172.1.0.102", "role": "MC SeaTrials", "ram": "5GB"},
            {"name": "GC02-DB", "ip": "172.1.0.105", "role": "MariaDB/Redis", "ram": "1GB"},
        ],
    },
    "OVH YYZ": {
        "name": "OVH YYZ Datacenter",
        "location": "Toronto, Ontario, Canada",
        "lat": 43.65,
        "lon": -79.38,
        "vms": [
            {"name": "S3 Storage", "ip": "192.99.0.2", "role": "Object Storage", "ram": "N/A"},
        ],
    },
    "Home": {
        "name": "Home Network",
        "location": "Montreal area, Quebec, Canada",
        "lat": 45.40,
        "lon": -73.90,
        "vms": [
            {"name": "Hermes Machine", "ip": "10.0.0.81", "role": "AI Agent / Desktop", "ram": "N/A"},
        ],
    },
}


# ---------------------------------------------------------------------------
# BGP peers (populate once you have an ARIN ASN)
# ---------------------------------------------------------------------------

@dataclass
class BGPPeer:
    asn: int
    name: str
    lat: float
    lon: float
    location: str

# Example BGP peers — replace with your actual peers once you have an ASN
BGP_PEERS: list[BGPPeer] = [
    # BGPPeer(asn=16276, name="OVH AS", lat=45.31, lon=-73.87, location="OVH BHS"),
    # BGPPeer(asn=14061, name="DigitalOcean", lat=40.71, lon=-74.00, location="New York, USA"),
]

# Your ASN (set once assigned by ARIN)
MY_ASN: int | None = None  # e.g. 12345
MY_ASN_LAT: float = 45.31
MY_ASN_LON: float = -73.87


# ---------------------------------------------------------------------------
# Protocol colour mapping (matches frontend)
# ---------------------------------------------------------------------------

PROTOCOL_COLORS = {
    "BGP":   "#9b59b6",  # purple
    "HTTP":  "#2ecc71",  # green
    "HTTPS": "#27ae60",  # dark green
    "SSH":   "#e67e22",  # orange
    "MINECRAFT": "#3498db",  # blue (game traffic)
    "DNS":   "#f1c40f",  # yellow
    "MYSQL":  "#e74c3c",  # red
    "REDIS":  "#c0392b",  # dark red
    "POSTGRES": "#e08e0b",  # amber
    "OTHER": "#ecf0f1",  # white
}

# Well-known port -> protocol label for classification
PORT_PROTOCOLS: dict[int, str] = {
    179:  "BGP",
    80:   "HTTP",
    443:  "HTTPS",
    22:   "SSH",
    53:   "DNS",
    25565: "MINECRAFT",
    25566: "MINECRAFT",
    19132: "MINECRAFT",
    3306: "MYSQL",
    3360: "MYSQL",
    6379: "REDIS",
    5432: "POSTGRES",
}


def classify_protocol(port: int, protocol_num: int) -> str:
    """Classify a flow by port number."""
    if port in PORT_PROTOCOLS:
        return PORT_PROTOCOLS[port]
    # Common ranges
    if 25560 <= port <= 25600:
        return "MINECRAFT"
    return "OTHER"