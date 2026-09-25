"""
NetTrace Map — Geolocation
MaxMind GeoLite2 integration with pre-configured infrastructure fallback.
"""

import os
import logging
from typing import Optional
from dataclasses import dataclass

import config

logger = logging.getLogger("nettrace.geo")

# ---------------------------------------------------------------------------
# MaxMind GeoLite2 reader (lazy-loaded)
# ---------------------------------------------------------------------------

_MMDB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "GeoLite2-City.mmdb")
_reader = None
_reader_loaded = False


def _get_reader():
    """Lazily load the MaxMind reader. Returns None if DB not present."""
    global _reader, _reader_loaded
    if _reader_loaded:
        return _reader
    _reader_loaded = True
    try:
        import geoip2.database
        abspath = os.path.abspath(_MMDB_PATH)
        if not os.path.isfile(abspath):
            logger.warning("GeoLite2 database not found at %s — using pre-configured IPs only", abspath)
            return None
        _reader = geoip2.database.Reader(abspath)
        logger.info("Loaded GeoLite2 database from %s", abspath)
    except ImportError:
        logger.warning("geoip2 package not installed — geolocation limited to pre-configured IPs")
    except Exception as e:
        logger.error("Failed to load GeoLite2 database: %s", e)
    return _reader


@dataclass
class GeoLocation:
    lat: float
    lon: float
    city: str = ""
    country: str = ""
    isp: str = ""
    asn: int = 0
    source: str = "geoip"  # "config", "geoip", or "fallback"


# Default fallback location (OVH BHS area)
_FALLBACK = GeoLocation(lat=45.31, lon=-73.87, city="Unknown", country="Unknown", source="fallback")


def geolocate_ip(ip: str) -> GeoLocation:
    """
    Geolocate an IP address.
    1. Check pre-configured machines first (exact match)
    2. Fall back to MaxMind GeoLite2
    3. Ultimate fallback: default coordinates
    """
    # 1. Pre-configured
    machine = config.IP_MAP.get(ip)
    if machine:
        return GeoLocation(
            lat=machine.lat,
            lon=machine.lon,
            city=machine.location,
            country="Canada" if "Canada" in machine.location else "",
            isp="OVH" if "OVH" in machine.name else "",
            source="config",
        )

    # 2. MaxMind GeoLite2
    reader = _get_reader()
    if reader:
        try:
            resp = reader.city(ip)
            return GeoLocation(
                lat=resp.location.latitude if resp.location.latitude else _FALLBACK.lat,
                lon=resp.location.longitude if resp.location.longitude else _FALLBACK.lon,
                city=resp.city.name or "",
                country=resp.country.name or "",
                isp=resp.traits.isp or "",
                source="geoip",
            )
        except Exception as e:
            logger.debug("GeoLite2 lookup failed for %s: %s", ip, e)

    # 3. Fallback
    return _FALLBACK


def geolocate_flow(src_ip: str, dst_ip: str) -> tuple[GeoLocation, GeoLocation]:
    """Geolocate both endpoints of a flow."""
    return geolocate_ip(src_ip), geolocate_ip(dst_ip)


def get_machine_info(ip: str) -> Optional[dict]:
    """Return pre-configured machine info if available."""
    m = config.IP_MAP.get(ip)
    if m:
        return {
            "name": m.name,
            "hostname": m.hostname,
            "ip": m.ip,
            "lat": m.lat,
            "lon": m.lon,
            "role": m.role,
            "location": m.location,
            "internal": m.internal,
        }
    return None


def all_machines() -> list[dict]:
    """Return all pre-configured machines for frontend display."""
    return [
        {
            "name": m.name,
            "hostname": m.hostname,
            "ip": m.ip,
            "lat": m.lat,
            "lon": m.lon,
            "role": m.role,
            "location": m.location,
            "internal": m.internal,
        }
        for m in config.MACHINES
    ]


def all_bgp_peers() -> list[dict]:
    """Return BGP peer info for frontend."""
    return [
        {
            "asn": p.asn,
            "name": p.name,
            "lat": p.lat,
            "lon": p.lon,
            "location": p.location,
        }
        for p in config.BGP_PEERS
    ]


if __name__ == "__main__":
    # Quick test
    for m in config.MACHINES:
        loc = geolocate_ip(m.ip)
        print(f"{m.name:25s} {m.ip:15s} -> {loc.lat:.2f}, {loc.lon:.2f} ({loc.source})")