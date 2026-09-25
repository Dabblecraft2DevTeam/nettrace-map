"""
NetTrace Map — Configuration
Pre-configured infrastructure endpoints for geolocation.
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


# ---------------------------------------------------------------------------
# Pre-configured infrastructure
# ---------------------------------------------------------------------------

MACHINES: list[Machine] = [
    Machine(
        name="OVH BHS Datacenter",
        hostname="ovh-bhs",
        ip="192.99.0.1",          # Placeholder — replace with your BHS public IP
        lat=45.31,
        lon=-73.87,
        role="XCP-NG Host / Factions / DB / Proxy / Router / XOCE",
        location="Beauharnois, Quebec, Canada",
    ),
    Machine(
        name="OVH YYZ Datacenter",
        hostname="ovh-yyz",
        ip="192.99.0.2",          # Placeholder — replace with your YYZ public IP
        lat=43.65,
        lon=-79.38,
        role="S3 Storage",
        location="Toronto, Ontario, Canada",
    ),
    Machine(
        name="Home Network",
        hostname="home",
        ip="10.0.0.1",            # Placeholder — your home gateway IP
        lat=45.40,
        lon=-73.90,
        role="Hermes Machine / Omada Network",
        location="Montreal area, Quebec, Canada",
        internal=True,
    ),
    Machine(
        name="DabbleBot VPS",
        hostname="dabblebot",
        ip="192.99.0.3",          # Placeholder — replace with DabbleBot public IP
        lat=45.31,
        lon=-73.87,
        role="DabbleBot VPS",
        location="Beauharnois, Quebec, Canada (OVH BHS)",
    ),
    Machine(
        name="Factions MC Server",
        hostname="factions",
        ip="172.1.0.104",
        lat=45.31,
        lon=-73.87,
        role="Minecraft Factions Server",
        location="OVH BHS (internal)",
        internal=True,
        external_ip="192.99.0.1",
    ),
    Machine(
        name="DB VM",
        hostname="db-vm",
        ip="172.1.0.105",
        lat=45.31,
        lon=-73.87,
        role="Database VM",
        location="OVH BHS (internal)",
        internal=True,
        external_ip="192.99.0.1",
    ),
]

# Quick lookup: IP -> Machine
IP_MAP: dict[str, Machine] = {m.ip: m for m in MACHINES}

# Also map hostname -> Machine for convenience
HOSTNAME_MAP: dict[str, Machine] = {m.hostname: m for m in MACHINES}


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
}


def classify_protocol(port: int, protocol_num: int) -> str:
    """Classify a flow by port number."""
    if port in PORT_PROTOCOLS:
        return PORT_PROTOCOLS[port]
    # Common ranges
    if 25560 <= port <= 25600:
        return "MINECRAFT"
    return "OTHER"