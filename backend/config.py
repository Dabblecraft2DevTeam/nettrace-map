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


# ---------------------------------------------------------------------------
# OVH global datacenter locations (backbone network)
# ---------------------------------------------------------------------------

OVH_DATACENTERS = [
    {"code": "BHS",  "name": "Beauharnois",         "country": "Canada",     "lat": 45.31, "lon": -73.87},
    {"code": "YYZ",  "name": "Toronto / Cambridge", "country": "Canada",     "lat": 43.65, "lon": -79.38},
    {"code": "TOR1", "name": "Toronto PoP",         "country": "Canada",     "lat": 43.65, "lon": -79.38},
    {"code": "GRA",  "name": "Gravelines",          "country": "France",     "lat": 50.98, "lon": 2.12},
    {"code": "RBX",  "name": "Roubaix",             "country": "France",     "lat": 50.69, "lon": 3.17},
    {"code": "SBG",  "name": "Strasbourg",          "country": "France",     "lat": 48.58, "lon": 7.75},
    {"code": "VHI",  "name": "Vint Hill",           "country": "USA",        "lat": 38.78, "lon": -77.70},
    {"code": "HIL",  "name": "Hillsboro",           "country": "USA",        "lat": 45.52, "lon": -122.99},
    {"code": "SGP",  "name": "Singapore",           "country": "Singapore",  "lat": 1.35,  "lon": 103.82},
    {"code": "SYD",  "name": "Sydney",              "country": "Australia",  "lat": -33.87, "lon": 151.21},
    {"code": "BOM",  "name": "Mumbai",              "country": "India",      "lat": 19.08, "lon": 72.88},
]

OVH_BACKBONE_CONNECTIONS = [
    ("BHS", "YYZ"), ("BHS", "VHI"), ("BHS", "GRA"), ("BHS", "HIL"),
    ("YYZ", "VHI"), ("YYZ", "GRA"),
    ("GRA", "RBX"), ("RBX", "SBG"), ("GRA", "SBG"),
    ("GRA", "VHI"), ("GRA", "SGP"), ("SBG", "SGP"),
    ("SGP", "SYD"), ("SGP", "BOM"),
    ("VHI", "HIL"), ("HIL", "SGP"), ("HIL", "SYD"),
    ("BOM", "SBG"),
]

# Custom connection lines (user-specific)
CUSTOM_LINES = [
    {
        "from": "BHS", "to": "Home",
        "from_coords": [45.31, -73.87], "to_coords": [45.40, -73.90],
        "label": "NetBird / VPN",
        "color": "#3498db", "dashed": False,
    },
    {
        "from": "BHS", "to": "YYZ",
        "from_coords": [45.31, -73.87], "to_coords": [43.65, -79.38],
        "label": "OVH private backbone (user traffic)",
        "color": "#e67e22", "dashed": True,
    },
]

# Internet Exchange Points (Canadian + major global)
IXP_POINTS = [
    {"code": "QIX",      "name": "Montreal Internet Exchange",   "city": "Montreal",         "country": "Canada",          "region": "Canadian", "lat": 45.50, "lon": -73.57},
    {"code": "TorIX",    "name": "Toronto Internet Exchange",    "city": "Toronto",          "country": "Canada",          "region": "Canadian", "lat": 43.65, "lon": -79.38},
    {"code": "FRE-IX",   "name": "Fredericton Internet Exchange","city": "Fredericton",      "country": "Canada",          "region": "Canadian", "lat": 45.96, "lon": -66.64},
    {"code": "YEG-IX",   "name": "Edmonton Internet Exchange",   "city": "Edmonton",         "country": "Canada",          "region": "Canadian", "lat": 53.55, "lon": -113.49},
    {"code": "WPG-IX",   "name": "Winnipeg Internet Exchange",   "city": "Winnipeg",         "country": "Canada",          "region": "Canadian", "lat": 49.88, "lon": -97.16},
    {"code": "BCIX",     "name": "BC Internet Exchange",         "city": "Vancouver",        "country": "Canada",          "region": "Canadian", "lat": 49.28, "lon": -123.12},
    {"code": "AMS-IX",   "name": "Amsterdam Internet Exchange",  "city": "Amsterdam",        "country": "Netherlands",     "region": "Global",   "lat": 52.37, "lon": 4.89},
    {"code": "LINX",     "name": "London Internet Exchange",     "city": "London",           "country": "United Kingdom",  "region": "Global",   "lat": 51.51, "lon": -0.01},
    {"code": "DE-CIX",   "name": "Deutsche Commercial Internet Exchange", "city": "Frankfurt", "country": "Germany",       "region": "Global",   "lat": 50.11, "lon": 8.68},
    {"code": "NYIIX",    "name": "New York International Internet Exchange", "city": "New York", "country": "USA",         "region": "Global",   "lat": 40.71, "lon": -74.01},
    {"code": "EQUINIX-ASH", "name": "Equinix Ashburn",           "city": "Ashburn",          "country": "USA",             "region": "Global",   "lat": 39.02, "lon": -77.45},
    {"code": "PAIX",     "name": "Palo Alto Internet Exchange",  "city": "Palo Alto",        "country": "USA",             "region": "Global",   "lat": 37.44, "lon": -122.16},
    {"code": "JPIX",     "name": "Japan Internet Exchange",      "city": "Tokyo",            "country": "Japan",           "region": "Global",   "lat": 35.69, "lon": 139.69},
    {"code": "HKIX",     "name": "Hong Kong Internet Exchange",  "city": "Hong Kong",        "country": "Hong Kong SAR",   "region": "Global",   "lat": 22.28, "lon": 114.14},
]