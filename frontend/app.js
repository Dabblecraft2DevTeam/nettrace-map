/*
 * NetTrace Map — Frontend Application
 * WebSocket client, Leaflet map, animation logic
 */

// ---------------------------------------------------------------------------
// Global state
// ---------------------------------------------------------------------------

let map;
let ws;
let cableLayer = null;
let landingLayer = null;
let machineMarkers = [];
let bgpLines = [];
let bgpMarkers = [];
let activeAnimations = [];  // Currently animating packet dots
let protocolColors = {};
let maxSimultaneousAnimations = 50;

// ---------------------------------------------------------------------------
// Protocol colors (fallback if not received from server)
// ---------------------------------------------------------------------------

const FALLBACK_COLORS = {
    "BGP":       "#9b59b6",
    "HTTP":      "#2ecc71",
    "HTTPS":     "#27ae60",
    "SSH":       "#e67e22",
    "MINECRAFT": "#3498db",
    "DNS":       "#f1c40f",
    "OTHER":     "#ecf0f1",
};

function protoColor(proto) {
    return protocolColors[proto] || FALLBACK_COLORS[proto] || "#ecf0f1";
}

// ---------------------------------------------------------------------------
// Initialize Leaflet map
// ---------------------------------------------------------------------------

function initMap() {
    map = L.map('map', {
        center: [45.31, -73.87],  // Default: OVH BHS
        zoom: 4,
        worldCopyJump: true,
        minZoom: 2,
        maxZoom: 18,
    });

    // Dark theme tile layer (CartoDB Dark Matter)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 19,
    }).addTo(map);

    // Load submarine cable overlay
    loadCables();
}

// ---------------------------------------------------------------------------
// Submarine cable overlay
// ---------------------------------------------------------------------------

async function loadCables() {
    try {
        const resp = await fetch('/api/cables');
        const geojson = await resp.json();

        cableLayer = L.geoJSON(geojson, {
            style: {
                color: '#1a6fa8',
                weight: 1,
                opacity: 0.3,
            },
            onEachFeature: function(feature, layer) {
                const name = feature.properties?.Name || 'Unknown cable';
                const length = feature.properties?.length || 'N/A';
                const rfs = feature.properties?.rfs || 'N/A';
                layer.bindPopup(
                    `<div class="machine-popup">
                        <h3>Submarine Cable</h3>
                        <div class="popup-field"><span class="popup-label">Name:</span> ${name}</div>
                        <div class="popup-field"><span class="popup-label">Length:</span> ${length}</div>
                        <div class="popup-field"><span class="popup-label">RFS:</span> ${rfs}</div>
                    </div>`
                );
            }
        }).addTo(map);

        console.log(`Loaded ${geojson.features?.length || 0} submarine cables`);
    } catch (e) {
        console.warn('Failed to load submarine cables:', e);
    }
}

// ---------------------------------------------------------------------------
// Landing points overlay
// ---------------------------------------------------------------------------

async function loadLandingPoints() {
    if (landingLayer) {
        map.removeLayer(landingLayer);
        landingLayer = null;
        return;
    }

    try {
        const resp = await fetch('/api/landing-points');
        const geojson = await resp.json();

        landingLayer = L.geoJSON(geojson, {
            pointToLayer: function(feature, latlng) {
                return L.circleMarker(latlng, {
                    radius: 3,
                    fillColor: '#1a6fa8',
                    color: '#1a6fa8',
                    weight: 1,
                    opacity: 0.6,
                    fillOpacity: 0.5,
                });
            },
            onEachFeature: function(feature, layer) {
                const name = feature.properties?.name || 'Unknown';
                layer.bindPopup(`<div class="machine-popup"><h3>Landing Point</h3><div class="popup-field">${name}</div></div>`);
            }
        }).addTo(map);

        console.log(`Loaded ${geojson.features?.length || 0} landing points`);
    } catch (e) {
        console.warn('Failed to load landing points:', e);
    }
}

// ---------------------------------------------------------------------------
// Machine markers
// ---------------------------------------------------------------------------

function addMachineMarkers(machines) {
    machines.forEach(m => {
        const icon = L.divIcon({
            className: m.internal ? 'machine-marker-internal' : 'machine-marker',
            iconSize: [14, 14],
            iconAnchor: [7, 7],
        });

        const marker = L.marker([m.lat, m.lon], { icon })
            .addTo(map);

        const internalBadge = m.internal ? '<span class="internal-badge">INTERNAL</span>' : '';
        marker.bindPopup(
            `<div class="machine-popup">
                <h3>${m.name} ${internalBadge}</h3>
                <div class="popup-field"><span class="popup-label">Hostname:</span> ${m.hostname}</div>
                <div class="popup-field"><span class="popup-label">IP:</span> ${m.ip}</div>
                <div class="popup-field"><span class="popup-label">Role:</span> ${m.role}</div>
                <div class="popup-field"><span class="popup-label">Location:</span> ${m.location}</div>
                <div class="popup-field"><span class="popup-label">Coords:</span> ${m.lat.toFixed(2)}°, ${m.lon.toFixed(2)}°</div>
            </div>`
        );

        machineMarkers.push(marker);
    });
}

// ---------------------------------------------------------------------------
// BGP visualization
// ---------------------------------------------------------------------------

function addBGPVisualization(bgpPeers, myAsn, myAsnCoords) {
    if (!myAsn || bgpPeers.length === 0) {
        console.log('No BGP peers configured (set MY_ASN in config.py when you have an ARIN ASN)');
        return;
    }

    const myLatLng = [myAsnCoords[0], myAsnCoords[1]];

    // Marker for our ASN
    const myIcon = L.divIcon({
        className: 'bgp-marker',
        iconSize: [18, 18],
        iconAnchor: [9, 9],
        html: '<div style="font-size:8px;text-align:center;color:#fff;font-weight:bold;line-height:16px;">AS</div>'
    });

    L.marker(myLatLng, { icon: myIcon })
        .addTo(map)
        .bindPopup(`<div class="machine-popup"><h3>Your AS${myAsn}</h3></div>`);

    bgpPeers.forEach(peer => {
        const peerLatLng = [peer.lat, peer.lon];

        // Persistent line for BGP peering
        const line = L.polyline([myLatLng, peerLatLng], {
            color: '#9b59b6',
            weight: 2,
            opacity: 0.4,
            dashArray: '8,6',
        }).addTo(map);

        line.bindPopup(
            `<div class="machine-popup">
                <h3>BGP Peering</h3>
                <div class="popup-field"><span class="popup-label">Peer:</span> AS${peer.asn} (${peer.name})</div>
                <div class="popup-field"><span class="popup-label">Location:</span> ${peer.location}</div>
            </div>`
        );

        bgpLines.push(line);

        // Peer marker
        const peerIcon = L.divIcon({
            className: 'bgp-marker',
            iconSize: [12, 12],
            iconAnchor: [6, 6],
        });

        const peerMarker = L.marker(peerLatLng, { icon: peerIcon })
            .addTo(map)
            .bindPopup(`<div class="machine-popup"><h3>AS${peer.asn}</h3><div class="popup-field">${peer.name}</div><div class="popup-field">${peer.location}</div></div>`);

        bgpMarkers.push(peerMarker);
    });
}

// ---------------------------------------------------------------------------
// Packet animation — great-circle arc with traveling dot
// ---------------------------------------------------------------------------

function animatePacket(flow) {
    if (activeAnimations.length >= maxSimultaneousAnimations) {
        // Remove oldest animation
        const oldest = activeAnimations.shift();
        if (oldest) oldest.cancel();
    }

    const srcLat = flow.src.lat;
    const srcLon = flow.src.lon;
    const dstLat = flow.dst.lat;
    const dstLon = flow.dst.lon;

    // Skip if same location
    if (srcLat === dstLat && srcLon === dstLon) return;

    const color = protoColor(flow.protocol);

    // Size based on bytes (logarithmic scale)
    const byteScale = Math.max(3, Math.min(10, 3 + Math.log10(Math.max(flow.bytes, 1))));

    // Duration based on distance (longer distance = longer travel time)
    const dist = map.distance([srcLat, srcLon], [dstLat, dstLon]);
    const duration = Math.max(1500, Math.min(6000, dist / 10));

    // Create great-circle arc (simplified — use bezier interpolation)
    const arcPoints = generateArc([srcLat, srcLon], [dstLat, dstLon], 64);

    // Draw the arc trail (semi-transparent, fades)
    const arcLine = L.polyline(arcPoints, {
        color: color,
        weight: 1.5,
        opacity: 0.15,
    }).addTo(map);

    // Create the moving dot
    const dotIcon = L.divIcon({
        className: 'packet-dot',
        iconSize: [byteScale * 2, byteScale * 2],
        iconAnchor: [byteScale, byteScale],
        html: `<div style="width:${byteScale * 2}px;height:${byteScale * 2}px;background:${color};border-radius:50%;box-shadow:0 0 ${byteScale * 2}px ${color};"></div>`
    });

    const dot = L.marker(arcPoints[0], { icon: dotIcon, zIndexOffset: 1000 }).addTo(map);

    let cancelled = false;
    const animation = {
        cancel: function() {
            cancelled = true;
            map.removeLayer(dot);
            // Fade out arc
            setTimeout(() => {
                if (map.hasLayer(arcLine)) map.removeLayer(arcLine);
            }, 500);
        }
    };
    activeAnimations.push(animation);

    // Animate along arc
    const startTime = performance.now();

    function frame(now) {
        if (cancelled) return;

        const elapsed = now - startTime;
        const t = Math.min(1, elapsed / duration);

        // Ease-in-out
        const easedT = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;

        const idx = Math.floor(easedT * (arcPoints.length - 1));
        const subT = (easedT * (arcPoints.length - 1)) - idx;
        const p1 = arcPoints[idx];
        const p2 = arcPoints[Math.min(idx + 1, arcPoints.length - 1)];

        const lat = p1[0] + (p2[0] - p1[0]) * subT;
        const lng = p1[1] + (p2[1] - p1[1]) * subT;

        dot.setLatLng([lat, lng]);

        // Fade arc as packet travels
        const arcOpacity = 0.15 * (1 - t * 0.5);
        arcLine.setStyle({ opacity: arcOpacity });

        if (t < 1) {
            requestAnimationFrame(frame);
        } else {
            // Animation complete
            map.removeLayer(dot);
            // Fade out arc line
            let fadeOpacity = 0.15;
            function fadeOut() {
                fadeOpacity -= 0.02;
                if (fadeOpacity <= 0) {
                    if (map.hasLayer(arcLine)) map.removeLayer(arcLine);
                    return;
                }
                arcLine.setStyle({ opacity: fadeOpacity });
                requestAnimationFrame(fadeOut);
            }
            requestAnimationFrame(fadeOut);

            // Remove from active list
            const idx2 = activeAnimations.indexOf(animation);
            if (idx2 >= 0) activeAnimations.splice(idx2, 1);
        }
    }

    requestAnimationFrame(frame);
}

// ---------------------------------------------------------------------------
// Great-circle arc generation (bezier curve for visual effect)
// ---------------------------------------------------------------------------

function generateArc(p1, p2, segments) {
    const lat1 = p1[0], lon1 = p1[1];
    const lat2 = p2[0], lon2 = p2[1];

    // Calculate midpoint with offset for arc effect
    const midLat = (lat1 + lat2) / 2;
    const midLon = (lon1 + lon2) / 2;

    // Perpendicular offset based on distance
    const dx = lon2 - lon1;
    const dy = lat2 - lat1;
    const dist = Math.sqrt(dx * dx + dy * dy);
    const offset = dist * 0.15;

    // Determine offset direction
    const angle = Math.atan2(dy, dx);
    const perpAngle = angle + Math.PI / 2;

    const ctrlLat = midLat + Math.sin(perpAngle) * offset;
    const ctrlLon = midLon + Math.cos(perpAngle) * offset;

    // Quadratic bezier
    const points = [];
    for (let i = 0; i <= segments; i++) {
        const t = i / segments;
        // Bezier: B(t) = (1-t)²P1 + 2(1-t)tP2 + t²P3
        const lat = (1 - t) * (1 - t) * lat1 + 2 * (1 - t) * t * ctrlLat + t * t * lat2;
        const lon = (1 - t) * (1 - t) * lon1 + 2 * (1 - t) * t * ctrlLon + t * t * lon2;
        points.push([lat, lon]);
    }

    return points;
}

// ---------------------------------------------------------------------------
// Flow list (sidebar)
// ---------------------------------------------------------------------------

function addFlowToList(flow) {
    const list = document.getElementById('flow-list');
    const item = document.createElement('div');
    item.className = 'flow-item';
    item.style.borderLeftColor = protoColor(flow.protocol);

    const protoBadge = `<span class="flow-protocol" style="background:${protoColor(flow.protocol)};color:#000;">${flow.protocol}</span>`;
    const route = `<div class="flow-route">${flow.src_ip}<span class="flow-arrow">→</span>${flow.dst_ip}</div>`;
    const meta = `<div class="flow-meta">:${flow.src_port} → :${flow.dst_port} · ${formatBytes(flow.bytes)} · ${flow.dst.city || 'Unknown'}</div>`;

    item.innerHTML = protoBadge + route + meta;
    list.insertBefore(item, list.firstChild);

    // Keep max 50 items
    while (list.children.length > 50) {
        list.removeChild(list.lastChild);
    }
}

// ---------------------------------------------------------------------------
// Stats display
// ---------------------------------------------------------------------------

function updateStats(stats) {
    document.getElementById('stat-total-flows').textContent = stats.total_flows.toLocaleString();
    document.getElementById('stat-total-bytes').textContent = formatBytes(stats.total_bytes);
    document.getElementById('stat-clients').textContent = stats.active_clients || 0;

    // Protocol breakdown
    const protoDiv = document.getElementById('protocol-breakdown');
    const protoCounts = stats.protocol_counts || {};
    const totalProto = Object.values(protoCounts).reduce((a, b) => a + b, 0) || 1;

    protoDiv.innerHTML = Object.entries(protoCounts)
        .sort((a, b) => b[1] - a[1])
        .map(([proto, count]) => {
            const pct = (count / totalProto * 100).toFixed(1);
            return `<div class="protocol-bar">
                <div class="protocol-bar-label">${proto}</div>
                <div class="protocol-bar-track">
                    <div class="protocol-bar-fill" style="width:${pct}%;background:${protoColor(proto)};"></div>
                </div>
                <div class="protocol-bar-count">${count}</div>
            </div>`;
        }).join('');

    // Top destinations
    const destDiv = document.getElementById('top-destinations');
    const topDests = stats.top_destinations || {};
    destDiv.innerHTML = Object.entries(topDests)
        .slice(0, 5)
        .map(([dest, count]) => `<div class="dest-item"><span>${dest}</span><span class="dest-count">${count}</span></div>`)
        .join('');
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + units[i];
}

// ---------------------------------------------------------------------------
// WebSocket connection
// ---------------------------------------------------------------------------

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    console.log('Connecting to WebSocket:', wsUrl);
    ws = new WebSocket(wsUrl);

    ws.onopen = function() {
        console.log('WebSocket connected');
        const status = document.getElementById('connection-status');
        status.className = 'status-connected';
        status.querySelector('.status-text').textContent = 'Connected';
    };

    ws.onmessage = function(event) {
        const msg = JSON.parse(event.data);

        switch (msg.type) {
            case 'init':
                protocolColors = msg.protocol_colors || FALLBACK_COLORS;
                addMachineMarkers(msg.machines || []);
                addBGPVisualization(msg.bgp_peers || [], msg.my_asn, msg.my_asn_coords);
                break;

            case 'flow':
                animatePacket(msg.flow);
                addFlowToList(msg.flow);
                break;

            case 'stats':
                updateStats(msg.stats);
                break;

            case 'pong':
                break;

            default:
                console.warn('Unknown message type:', msg.type);
        }
    };

    ws.onclose = function() {
        console.log('WebSocket disconnected — reconnecting in 3s');
        const status = document.getElementById('connection-status');
        status.className = 'status-disconnected';
        status.querySelector('.status-text').textContent = 'Disconnected';
        setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = function(err) {
        console.error('WebSocket error:', err);
    };

    // Heartbeat
    setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
        }
    }, 30000);
}

// ---------------------------------------------------------------------------
// Control toggles
// ---------------------------------------------------------------------------

function setupControls() {
    document.getElementById('toggle-cables').addEventListener('change', function(e) {
        if (cableLayer) {
            if (e.target.checked) {
                cableLayer.addTo(map);
            } else {
                map.removeLayer(cableLayer);
            }
        }
    });

    document.getElementById('toggle-landing').addEventListener('change', function(e) {
        if (e.target.checked) {
            loadLandingPoints();
        } else if (landingLayer) {
            map.removeLayer(landingLayer);
            landingLayer = null;
        }
    });

    document.getElementById('toggle-bgp').addEventListener('change', function(e) {
        const show = e.target.checked;
        bgpLines.forEach(l => show ? l.addTo(map) : map.removeLayer(l));
        bgpMarkers.forEach(m => show ? m.addTo(map) : map.removeLayer(m));
    });

    document.getElementById('toggle-machines').addEventListener('change', function(e) {
        const show = e.target.checked;
        machineMarkers.forEach(m => show ? m.addTo(map) : map.removeLayer(m));
    });
}

// ---------------------------------------------------------------------------
// Initialize
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', function() {
    initMap();
    setupControls();
    connectWebSocket();
});