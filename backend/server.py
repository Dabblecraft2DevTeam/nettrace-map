"""
NetTrace Map — FastAPI Backend
NetFlow v9/v5 collector + WebSocket streaming to frontend.
"""

import asyncio
import json
import logging
import os
import struct
import time
from collections import deque
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import config
import geo

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("nettrace.server")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="NetTrace Map", version="1.0.0")

# Connected WebSocket clients
ws_clients: set[WebSocket] = set()

# Flow statistics
flow_stats = {
    "total_flows": 0,
    "total_bytes": 0,
    "top_destinations": {},  # ip -> count
    "protocol_counts": {},   # protocol -> count
    "recent_flows": deque(maxlen=200),
}


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.add(ws)
    logger.info("WebSocket client connected (%d total)", len(ws_clients))

    # Send initial data: machines, BGP peers, recent flows
    await ws.send_json({
        "type": "init",
        "machines": geo.all_machines(),
        "bgp_peers": geo.all_bgp_peers(),
        "my_asn": config.MY_ASN,
        "my_asn_coords": [config.MY_ASN_LAT, config.MY_ASN_LON],
        "protocol_colors": config.PROTOCOL_COLORS,
    })

    # Send recent flows
    for flow in flow_stats["recent_flows"]:
        await ws.send_json({"type": "flow", "flow": flow})

    try:
        while True:
            # Keep connection alive; clients can send pings
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_clients.discard(ws)
        logger.info("WebSocket client disconnected (%d total)", len(ws_clients))


async def broadcast_flow(flow_data: dict):
    """Send a flow event to all connected WebSocket clients."""
    dead = set()
    for ws in ws_clients:
        try:
            await ws.send_json({"type": "flow", "flow": flow_data})
        except Exception:
            dead.add(ws)
    ws_clients.difference_update(dead)


async def broadcast_stats():
    """Send updated stats to all connected clients."""
    dead = set()
    stats = {
        "type": "stats",
        "stats": {
            "total_flows": flow_stats["total_flows"],
            "total_bytes": flow_stats["total_bytes"],
            "top_destinations": dict(
                sorted(flow_stats["top_destinations"].items(), key=lambda x: -x[1])[:10]
            ),
            "protocol_counts": dict(flow_stats["protocol_counts"]),
            "active_clients": len(ws_clients),
        },
    }
    for ws in ws_clients:
        try:
            await ws.send_json(stats)
        except Exception:
            dead.add(ws)
    ws_clients.difference_update(dead)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.get("/api/machines")
async def get_machines():
    return JSONResponse(geo.all_machines())


@app.get("/api/bgp-peers")
async def get_bgp_peers():
    return JSONResponse(geo.all_bgp_peers())


@app.get("/api/stats")
async def get_stats():
    return JSONResponse({
        "total_flows": flow_stats["total_flows"],
        "total_bytes": flow_stats["total_bytes"],
        "top_destinations": dict(
            sorted(flow_stats["top_destinations"].items(), key=lambda x: -x[1])[:10]
        ),
        "protocol_counts": dict(flow_stats["protocol_counts"]),
        "active_clients": len(ws_clients),
    })


@app.get("/api/cables")
async def get_cables():
    """Serve submarine cable GeoJSON."""
    path = os.path.join(os.path.dirname(__file__), "..", "data", "cables.geojson")
    return FileResponse(os.path.abspath(path), media_type="application/json")


@app.get("/api/landing-points")
async def get_landing_points():
    """Serve landing points GeoJSON."""
    path = os.path.join(os.path.dirname(__file__), "..", "data", "landing_points.geojson")
    return FileResponse(os.path.abspath(path), media_type="application/json")


# ---------------------------------------------------------------------------
# Flow processing
# ---------------------------------------------------------------------------

def process_flow(src_ip: str, dst_ip: str, src_port: int, dst_port: int,
                 protocol: int, bytes_count: int, packets: int = 0):
    """Process a single NetFlow record: geolocate, classify, broadcast."""
    proto_label = config.classify_protocol(dst_port, protocol)

    src_geo, dst_geo = geo.geolocate_flow(src_ip, dst_ip)

    flow = {
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "src_port": src_port,
        "dst_port": dst_port,
        "protocol": proto_label,
        "protocol_num": protocol,
        "bytes": bytes_count,
        "packets": packets,
        "timestamp": time.time(),
        "src": {
            "lat": src_geo.lat,
            "lon": src_geo.lon,
            "city": src_geo.city,
            "country": src_geo.country,
            "source": src_geo.source,
        },
        "dst": {
            "lat": dst_geo.lat,
            "lon": dst_geo.lon,
            "city": dst_geo.city,
            "country": dst_geo.country,
            "source": dst_geo.source,
        },
    }

    # Update stats
    flow_stats["total_flows"] += 1
    flow_stats["total_bytes"] += bytes_count
    flow_stats["recent_flows"].append(flow)

    dst_key = f"{dst_ip} ({dst_geo.city or 'Unknown'})"
    flow_stats["top_destinations"][dst_key] = flow_stats["top_destinations"].get(dst_key, 0) + 1
    flow_stats["protocol_counts"][proto_label] = flow_stats["protocol_counts"].get(proto_label, 0) + 1

    # Broadcast asynchronously
    asyncio.ensure_future(broadcast_flow(flow))


# ---------------------------------------------------------------------------
# NetFlow collector (runs in background)
# ---------------------------------------------------------------------------

class NetFlowCollector:
    """
    UDP listener for NetFlow v5/v9 packets.
    Uses a lightweight parser — no external NetFlow library required.
    For full v9 template support, consider python-netflow (see requirements.txt).
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 2055):
        self.host = host
        self.port = port
        self.transport: Optional[asyncio.DatagramTransport] = None
        self._v9_templates: dict = {}

    async def start(self):
        loop = asyncio.get_event_loop()
        self.transport, _ = await loop.create_datagram_endpoint(
            lambda: NetFlowProtocol(self),
            local_addr=(self.host, self.port),
        )
        logger.info("NetFlow collector listening on %s:%d (UDP)", self.host, self.port)

    def stop(self):
        if self.transport:
            self.transport.close()


class NetFlowProtocol(asyncio.DatagramProtocol):
    """Datagram protocol handler for NetFlow packets."""

    def __init__(self, collector: NetFlowCollector):
        self.collector = collector

    def datagram_received(self, data: bytes, addr):
        try:
            self._parse_netflow(data, addr)
        except Exception as e:
            logger.debug("NetFlow parse error from %s: %s", addr, e)

    def _parse_netflow(self, data: bytes, addr):
        if len(data) < 20:
            return

        # NetFlow header: first 2 bytes = version
        version = struct.unpack("!H", data[0:2])[0]

        if version == 5:
            self._parse_v5(data, addr)
        elif version == 9:
            self._parse_v9(data, addr)
        else:
            logger.debug("Unsupported NetFlow version %d from %s", version, addr)

    def _parse_v5(self, data: bytes, addr):
        """Parse NetFlow v5 record."""
        # Header: version(2) + count(2) + sys_uptime(4) + unix_secs(4) + unix_nsecs(4) + flow_seq(4) + engine_type(1) + engine_id(1) + sampling(2) = 24
        if len(data) < 24:
            return

        count = struct.unpack("!H", data[2:4])[0]
        offset = 24

        for i in range(count):
            if offset + 48 > len(data):
                break

            record = data[offset:offset + 48]
            # v5 record: srcaddr(4) dstaddr(4) nexthop(4) input(2) output(2) dPkts(4) dOctets(4) first(4) last(4) srcport(2) dstport(2) pad1(1) tcp_flags(1) prot(1) tos(1) src_as(2) dst_as(2) src_mask(1) dst_mask(1) pad2(2)
            src_ip = ".".join(str(b) for b in record[0:4])
            dst_ip = ".".join(str(b) for b in record[4:8])
            d_pkts = struct.unpack("!I", record[16:20])[0]
            d_octets = struct.unpack("!I", record[20:24])[0]
            src_port = struct.unpack("!H", record[32:34])[0]
            dst_port = struct.unpack("!H", record[34:36])[0]
            protocol = record[38]

            process_flow(src_ip, dst_ip, src_port, dst_port, protocol, d_octets, d_pkts)
            offset += 48

    def _parse_v9(self, data: bytes, addr):
        """
        Parse NetFlow v9 (IPFIX) packets.
        v9 uses templates — this is a basic implementation.
        For production use, install python-netflow (in requirements.txt, optional).
        """
        # Header: version(2) + count(2) + sys_uptime(4) + unix_secs(4) + package_seq(4) + source_id(4) = 20
        if len(data) < 20:
            return

        count = struct.unpack("!H", data[2:4])[0]
        offset = 20
        template_id = 0  # flowset ID for data

        for _ in range(count):
            if offset + 4 > len(data):
                break

            flowset_id = struct.unpack("!H", data[offset:offset + 2])[0]
            flowset_len = struct.unpack("!H", data[offset + 2:offset + 4])[0]

            if flowset_len < 4 or offset + flowset_len > len(data):
                break

            flowset_data = data[offset + 4:offset + flowset_len]

            if flowset_id == 0:
                # Template FlowSet
                self._parse_v9_template(flowset_data)
            elif flowset_id == 1:
                # Options Template
                pass
            else:
                # Data FlowSet — use stored template
                self._parse_v9_data(flowset_id, flowset_data)

            offset += flowset_len

    def _parse_v9_template(self, data: bytes):
        """Parse v9 template definitions."""
        pos = 0
        while pos + 4 <= len(data):
            template_id = struct.unpack("!H", data[pos:pos + 2])[0]
            field_count = struct.unpack("!H", data[pos + 2:pos + 4])[0]
            pos += 4

            fields = []
            for _ in range(field_count):
                if pos + 4 > len(data):
                    break
                field_type = struct.unpack("!H", data[pos:pos + 2])[0]
                field_len = struct.unpack("!H", data[pos + 2:pos + 4])[0]
                fields.append((field_type, field_len))
                pos += 4

            self.collector._v9_templates[template_id] = fields

    def _parse_v9_data(self, flowset_id: int, data: bytes):
        """Parse v9 data records using a stored template."""
        template = self.collector._v9_templates.get(flowset_id)
        if not template:
            return  # No template yet — skip

        # Common v9 field types
        # 8=src IPv4, 12=dst IPv4, 7=src port, 11=dst port, 4=protocol, 85=sysid, 2=pkt count, 1=byte count
        pos = 0
        record_len = sum(f[1] for f in template)

        while pos + record_len <= len(data):
            src_ip = dst_ip = "0.0.0.0"
            src_port = dst_port = 0
            protocol = 0
            bytes_count = 0
            packets = 0

            field_pos = pos
            for field_type, field_len in template:
                if field_pos + field_len > len(data):
                    break

                raw = data[field_pos:field_pos + field_len]

                if field_type == 8:  # SRC_ADDR (IPv4)
                    src_ip = ".".join(str(b) for b in raw[:4])
                elif field_type == 12:  # DST_ADDR (IPv4)
                    dst_ip = ".".join(str(b) for b in raw[:4])
                elif field_type == 7:  # L4_SRC_PORT
                    src_port = struct.unpack("!H", raw[:2])[0] if field_len >= 2 else 0
                elif field_type == 11:  # L4_DST_PORT
                    dst_port = struct.unpack("!H", raw[:2])[0] if field_len >= 2 else 0
                elif field_type == 4:  # PROTOCOL
                    protocol = raw[0] if field_len >= 1 else 0
                elif field_type == 2:  # IN_PKTS
                    bytes_count = int.from_bytes(raw, "big")
                elif field_type == 1:  # IN_BYTES
                    bytes_count = int.from_bytes(raw, "big")
                elif field_type == 86:  # OUT_BYTES
                    bytes_count = int.from_bytes(raw, "big")

                field_pos += field_len

            if src_ip != "0.0.0.0" and dst_ip != "0.0.0.0":
                process_flow(src_ip, dst_ip, src_port, dst_port, protocol, bytes_count, packets)

            pos += record_len


# ---------------------------------------------------------------------------
# Demo mode — generates simulated flows for testing without NetFlow source
# ---------------------------------------------------------------------------

DEMO_FLOWS = [
    # (src_ip, dst_ip, dst_port, protocol_num, bytes_range)
    ("10.0.0.1", "192.99.0.1", 443, 6, (500, 50000)),       # Home -> OVH BHS HTTPS
    ("10.0.0.1", "192.99.0.3", 22, 6, (200, 5000)),         # Home -> DabbleBot SSH
    ("192.99.0.1", "192.99.0.2", 443, 6, (1000, 100000)),   # BHS -> YYZ HTTPS
    ("192.99.0.3", "172.1.0.104", 25565, 6, (200, 20000)),  # DabbleBot -> Factions MC
    ("192.99.0.1", "172.1.0.105", 5432, 6, (500, 30000)),   # BHS -> DB VM (PostgreSQL)
    ("10.0.0.1", "192.99.0.1", 53, 17, (100, 2000)),        # Home -> OVH DNS
    ("192.99.0.1", "10.0.0.1", 443, 6, (500, 20000)),       # OVH -> Home HTTPS
]

import random


async def demo_flow_generator():
    """Generate simulated flows every few seconds for demo/testing."""
    logger.info("Demo mode active — generating simulated flows")
    while True:
        await asyncio.sleep(1.5 + random.random() * 2.5)

        flow_spec = random.choice(DEMO_FLOWS)
        src_ip, dst_ip, dst_port, protocol, byte_range = flow_spec
        bytes_count = random.randint(byte_range[0], byte_range[1])
        src_port = random.randint(1024, 65535)

        process_flow(src_ip, dst_ip, src_port, dst_port, protocol, bytes_count, 1)

        # Periodically broadcast stats
        if flow_stats["total_flows"] % 10 == 0:
            await broadcast_stats()


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------

collector: Optional[NetFlowCollector] = None
demo_task: Optional[asyncio.Task] = None


@app.on_event("startup")
async def startup():
    global collector, demo_task

    # Start NetFlow collector
    nf_host = os.environ.get("NETTRACE_NF_HOST", "0.0.0.0")
    nf_port = int(os.environ.get("NETTRACE_NF_PORT", "2055"))
    collector = NetFlowCollector(host=nf_host, port=nf_port)
    try:
        await collector.start()
    except Exception as e:
        logger.warning("NetFlow collector failed to start: %s — using demo mode only", e)

    # Start demo mode if enabled (default: on when no flows arriving)
    demo_mode = os.environ.get("NETTRACE_DEMO", "1").lower() in ("1", "true", "yes")
    if demo_mode:
        demo_task = asyncio.create_task(demo_flow_generator())

    # Serve frontend static files
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
    app.mount("/", StaticFiles(directory=os.path.abspath(frontend_dir), html=True), name="frontend")


@app.on_event("shutdown")
async def shutdown():
    if collector:
        collector.stop()
    if demo_task:
        demo_task.cancel()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )