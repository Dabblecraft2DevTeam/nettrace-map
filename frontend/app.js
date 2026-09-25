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

// Cluster state
let clustersData = {};         // cluster name -> cluster dict from backend
let activeClusterName = null;  // currently displayed cluster
let clusterVmPositions = {};   // cluster name -> { ip -> {x, y, name, role} }
let clusterSvgRoot = null;     // current SVG element for the active cluster
let clusterPacketAnimations = []; // active in-cluster packet animations
let maxClusterPackets = 30;

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
    "MYSQL":     "#e74c3c",
    "REDIS":     "#c0392b",
    "POSTGRES":  "#e08e0b",
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

    // Dark theme tile layer (OpenStreetMap via CARTO dark style fallback)
    // Primary: CARTO Dark Matter (free, no API key, based on OpenStreetMap data)
    // Fallback: Stadia AlidadeSmoothDark (also free, OSM-based)
    const tileLayers = {
        dark: L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
            maxZoom: 19,
            subdomains: 'abcd'
        }),
        osm: L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 19,
            subdomains: 'abc'
        }),
        stadiaDark: L.tileLayer('https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://stadiamaps.com/">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 20,
            subdomains: 'abc'
        })
    };

    // Default to OpenStreetMap (no API key ever required)
    tileLayers.osm.addTo(map);

    // Layer control for switching map styles
    L.control.layers({
        "Dark (CARTO)": tileLayers.dark,
        "OpenStreetMap": tileLayers.osm,
        "Stadia Dark": tileLayers.stadiaDark
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
// Cluster visualization — virtual server box with internal VM nodes
// ---------------------------------------------------------------------------

/**
 * Render the cluster selector buttons in the sidebar.
 * Clicking a button opens the cluster overlay panel.
 */
function renderClusterButtons() {
    const container = document.getElementById('cluster-buttons');
    if (!container) return;
    container.innerHTML = '';

    Object.entries(clustersData).forEach(([name, cluster]) => {
        const btn = document.createElement('button');
        btn.className = 'cluster-btn';
        btn.dataset.clusterName = name;
        const vmCount = cluster.vms ? cluster.vms.length : 0;
        btn.innerHTML = `<div class="cluster-btn-name">${cluster.name || name}</div>`
            + `<div class="cluster-btn-meta">${vmCount} VM${vmCount !== 1 ? 's' : ''} · ${cluster.location || ''}</div>`;
        btn.addEventListener('click', () => openCluster(name));
        container.appendChild(btn);
    });

    if (Object.keys(clustersData).length === 0) {
        container.innerHTML = '<div style="color:#666;font-size:11px;">No clusters configured</div>';
    }
}

/**
 * Open the cluster overlay panel and render the diagram.
 */
function openCluster(name) {
    const cluster = clustersData[name];
    if (!cluster) return;

    activeClusterName = name;

    // Update sidebar button states
    document.querySelectorAll('.cluster-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.clusterName === name);
    });

    // Update title
    document.getElementById('cluster-title').textContent = cluster.name || name;

    // Render the SVG diagram
    renderClusterDiagram(name, cluster);

    // Show the overlay
    document.getElementById('cluster-overlay').classList.remove('hidden');
}

/**
 * Close the cluster overlay panel.
 */
function closeCluster() {
    document.getElementById('cluster-overlay').classList.add('hidden');
    activeClusterName = null;
    clusterSvgRoot = null;
    // Clear in-cluster animations
    clusterPacketAnimations.forEach(a => { if (a.cancel) a.cancel(); });
    clusterPacketAnimations = [];
    document.querySelectorAll('.cluster-btn').forEach(b => b.classList.remove('active'));
}

/**
 * Layout VM nodes inside the cluster SVG.
 * Router (OPNsense) is placed at the left edge of the box.
 * Other VMs are arranged in a grid to the right.
 *
 * Returns a dict: ip -> {x, y, w, h, name, role, isRouter}
 */
function layoutClusterVMs(cluster) {
    const vms = cluster.vms || [];
    const positions = {};

    // Find the router VM (OPNsense edge)
    const edgeIp = cluster.edge_ip;
    let routerVm = null;
    const otherVms = [];
    vms.forEach(vm => {
        if (vm.role && /OPNsense|Edge|Router/i.test(vm.role)) {
            routerVm = vm;
        } else if (edgeIp && vm.ip === edgeIp) {
            routerVm = vm;
        } else {
            otherVms.push(vm);
        }
    });
    // If no router found, use first VM as edge
    if (!routerVm && vms.length > 0) routerVm = vms[0];

    const nodeW = 110;
    const nodeH = 54;
    const gapX = 24;
    const gapY = 18;
    const routerX = 30;
    const routerY = 160;

    if (routerVm) {
        positions[routerVm.ip] = {
            x: routerX, y: routerY, w: nodeW, h: nodeH,
            name: routerVm.name, role: routerVm.role,
            ram: routerVm.ram, isRouter: true,
        };
    }

    // Arrange other VMs in 2 columns
    const cols = 2;
    const startX = 190;
    const startY = 40;
    otherVms.forEach((vm, i) => {
        const col = i % cols;
        const row = Math.floor(i / cols);
        positions[vm.ip] = {
            x: startX + col * (nodeW + gapX),
            y: startY + row * (nodeH + gapY),
            w: nodeW, h: nodeH,
            name: vm.name, role: vm.role,
            ram: vm.ram, isRouter: false,
        };
    });

    return positions;
}

/**
 * Render the cluster SVG diagram with VM nodes inside a dashed box.
 */
function renderClusterDiagram(name, cluster) {
    const diagramDiv = document.getElementById('cluster-diagram');
    const positions = layoutClusterVMs(cluster);
    clusterVmPositions[name] = positions;

    // Compute SVG canvas size
    const allPos = Object.values(positions);
    const maxX = allPos.length ? Math.max(...allPos.map(p => p.x + p.w)) : 400;
    const maxY = allPos.length ? Math.max(...allPos.map(p => p.y + p.h)) : 300;
    const padRight = 30;
    const padBottom = 30;
    const svgW = Math.max(520, maxX + padRight);
    const svgH = Math.max(380, maxY + padBottom);

    // Build SVG
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('class', 'cluster-svg');
    svg.setAttribute('viewBox', `0 0 ${svgW} ${svgH}`);
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');

    // Background box (virtual server container)
    const boxX = 15, boxY = 15;
    const boxW = svgW - 30, boxH = svgH - 30;
    const boxRect = document.createElementNS(ns, 'rect');
    boxRect.setAttribute('class', 'cluster-box-rect');
    boxRect.setAttribute('x', boxX);
    boxRect.setAttribute('y', boxY);
    boxRect.setAttribute('width', boxW);
    boxRect.setAttribute('height', boxH);
    boxRect.setAttribute('rx', 10);
    boxRect.setAttribute('ry', 10);
    svg.appendChild(boxRect);

    // Box label (top-left)
    const boxLabel = document.createElementNS(ns, 'text');
    boxLabel.setAttribute('class', 'cluster-box-label');
    boxLabel.setAttribute('x', boxX + 12);
    boxLabel.setAttribute('y', boxY + 22);
    boxLabel.textContent = cluster.name || name;
    svg.appendChild(boxLabel);

    // Edge label (public IP)
    if (cluster.edge_ip) {
        const edgeLabel = document.createElementNS(ns, 'text');
        edgeLabel.setAttribute('class', 'cluster-edge-label');
        edgeLabel.setAttribute('x', boxX + 12);
        edgeLabel.setAttribute('y', boxY + 36);
        edgeLabel.textContent = `Edge: ${cluster.edge_ip}`;
        svg.appendChild(edgeLabel);
    }

    // Draw faint internal flow reference lines (router -> each VM)
    const routerPos = Object.values(positions).find(p => p.isRouter);
    if (routerPos) {
        Object.values(positions).forEach(p => {
            if (p.isRouter) return;
            const line = document.createElementNS(ns, 'line');
            line.setAttribute('class', 'internal-flow-line');
            line.setAttribute('x1', routerPos.x + routerPos.w);
            line.setAttribute('y1', routerPos.y + routerPos.h / 2);
            line.setAttribute('x2', p.x);
            line.setAttribute('y2', p.y + p.h / 2);
            svg.appendChild(line);
        });
    }

    // Draw VM nodes
    Object.entries(positions).forEach(([ip, pos]) => {
        const g = document.createElementNS(ns, 'g');
        g.setAttribute('class', pos.isRouter ? 'vm-node vm-node-router' : 'vm-node');
        g.setAttribute('transform', `translate(${pos.x}, ${pos.y})`);

        // Rect
        const rect = document.createElementNS(ns, 'rect');
        rect.setAttribute('class', 'vm-node-rect');
        rect.setAttribute('x', 0);
        rect.setAttribute('y', 0);
        rect.setAttribute('width', pos.w);
        rect.setAttribute('height', pos.h);
        rect.setAttribute('rx', 6);
        rect.setAttribute('ry', 6);
        g.appendChild(rect);

        // Title
        const title = document.createElementNS(ns, 'text');
        title.setAttribute('class', 'vm-node-title');
        title.setAttribute('x', pos.w / 2);
        title.setAttribute('y', 18);
        // Shorten name for display
        let displayName = pos.name.replace(/^GC02-/, '');
        if (displayName.length > 14) displayName = displayName.substring(0, 13) + '…';
        title.textContent = displayName;
        g.appendChild(title);

        // Role
        const role = document.createElementNS(ns, 'text');
        role.setAttribute('class', 'vm-node-role');
        role.setAttribute('x', pos.w / 2);
        role.setAttribute('y', 32);
        let roleText = pos.role || '';
        if (roleText.length > 16) roleText = roleText.substring(0, 15) + '…';
        role.textContent = roleText;
        g.appendChild(role);

        // IP
        const ipText = document.createElementNS(ns, 'text');
        ipText.setAttribute('class', 'vm-node-ip');
        ipText.setAttribute('x', pos.w / 2);
        ipText.setAttribute('y', 46);
        ipText.textContent = ip;
        g.appendChild(ipText);

        // Router badge
        if (pos.isRouter) {
            const badge = document.createElementNS(ns, 'text');
            badge.setAttribute('class', 'vm-node-badge');
            badge.setAttribute('x', pos.w / 2);
            badge.setAttribute('y', -4);
            badge.textContent = 'EDGE';
            g.appendChild(badge);
        }

        // Tooltip via title
        const ttlelem = document.createElementNS(ns, 'title');
        ttlelem.textContent = `${pos.name}\n${pos.role || ''}\n${ip}${pos.ram ? ' · ' + pos.ram : ''}`;
        g.appendChild(ttlelem);

        svg.appendChild(g);
    });

    diagramDiv.innerHTML = '';
    diagramDiv.appendChild(svg);
    clusterSvgRoot = svg;
}

/**
 * Get the center point of a VM node in the active cluster SVG coordinates.
 */
function getVmCenter(ip) {
    if (!activeClusterName) return null;
    const positions = clusterVmPositions[activeClusterName];
    if (!positions || !positions[ip]) return null;
    const p = positions[ip];
    return { x: p.x + p.w / 2, y: p.y + p.h / 2 };
}

/**
 * Animate a packet inside the cluster diagram based on flow data.
 * - enters_cluster: external -> internal VM (router -> VM arrow)
 * - internal_flow: VM -> VM inside same cluster
 */
function animateClusterPacket(flow) {
    if (!activeClusterName || !clusterSvgRoot) return;

    const overlay = document.getElementById('cluster-overlay');
    if (overlay.classList.contains('hidden')) return;

    // Enforce max simultaneous in-cluster animations
    if (clusterPacketAnimations.length >= maxClusterPackets) {
        const oldest = clusterPacketAnimations.shift();
        if (oldest && oldest.cancel) oldest.cancel();
    }

    const color = protoColor(flow.protocol);
    const ns = 'http://www.w3.org/2000/svg';

    let fromPos = null;
    let toPos = null;
    let label = '';

    if (flow.internal_flow && flow.src_vm && flow.dst_vm
        && flow.src_vm.cluster === activeClusterName
        && flow.dst_vm.cluster === activeClusterName) {
        // Internal VM-to-VM flow
        fromPos = getVmCenter(flow.src_vm.ip);
        toPos = getVmCenter(flow.dst_vm.ip);
        label = 'internal';
    } else if (flow.enters_cluster && flow.dst_vm
               && flow.dst_vm.cluster === activeClusterName) {
        // External -> internal VM: route through router
        const routerPos = Object.values(clusterVmPositions[activeClusterName])
            .find(p => p.isRouter);
        if (routerPos) {
            fromPos = { x: routerPos.x + routerPos.w / 2, y: routerPos.y + routerPos.h / 2 };
        }
        toPos = getVmCenter(flow.dst_vm.ip);
        label = 'external';
    } else {
        return; // Not relevant to this cluster
    }

    if (!fromPos || !toPos) return;
    if (fromPos.x === toPos.x && fromPos.y === toPos.y) return;

    // Create trail path (straight line with slight curve)
    const midX = (fromPos.x + toPos.x) / 2;
    const midY = (fromPos.y + toPos.y) / 2;
    const dx = toPos.x - fromPos.x;
    const dy = toPos.y - fromPos.y;
    const dist = Math.sqrt(dx * dx + dy * dy);
    const offset = dist * 0.12;
    // Perpendicular offset
    const perpAngle = Math.atan2(dy, dx) + Math.PI / 2;
    const ctrlX = midX + Math.cos(perpAngle) * offset;
    const ctrlY = midY + Math.sin(perpAngle) * offset;

    const pathD = `M ${fromPos.x} ${fromPos.y} Q ${ctrlX} ${ctrlY} ${toPos.x} ${toPos.y}`;

    // Trail
    const trail = document.createElementNS(ns, 'path');
    trail.setAttribute('class', 'cluster-packet-trail');
    trail.setAttribute('d', pathD);
    trail.setAttribute('stroke', color);
    trail.setAttribute('stroke-width', 1.5);
    clusterSvgRoot.appendChild(trail);

    // Packet dot
    const radius = Math.max(2.5, Math.min(6, 2.5 + Math.log10(Math.max(flow.bytes, 1)) * 0.5));
    const dot = document.createElementNS(ns, 'circle');
    dot.setAttribute('class', 'cluster-packet-dot');
    dot.setAttribute('cx', fromPos.x);
    dot.setAttribute('cy', fromPos.y);
    dot.setAttribute('r', radius);
    dot.setAttribute('fill', color);
    dot.style.filter = `drop-shadow(0 0 ${radius * 2}px ${color})`;
    clusterSvgRoot.appendChild(dot);

    // Arrowhead at destination
    const arrow = document.createElementNS(ns, 'polygon');
    arrow.setAttribute('class', 'cluster-packet-dot');
    arrow.setAttribute('fill', color);
    arrow.setAttribute('opacity', '0');
    clusterSvgRoot.appendChild(arrow);

    let cancelled = false;
    const anim = {
        cancel: function() {
            cancelled = true;
            if (trail.parentNode) trail.parentNode.removeChild(trail);
            if (dot.parentNode) dot.parentNode.removeChild(dot);
            if (arrow.parentNode) arrow.parentNode.removeChild(arrow);
        }
    };
    clusterPacketAnimations.push(anim);

    // Animate
    const duration = Math.max(600, Math.min(2000, dist * 3));
    const startTime = performance.now();

    function frame(now) {
        if (cancelled) return;
        const elapsed = now - startTime;
        const t = Math.min(1, elapsed / duration);
        const eased = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;

        // Quadratic bezier point
        const u = 1 - eased;
        const x = u * u * fromPos.x + 2 * u * eased * ctrlX + eased * eased * toPos.x;
        const y = u * u * fromPos.y + 2 * u * eased * ctrlY + eased * eased * toPos.y;
        dot.setAttribute('cx', x);
        dot.setAttribute('cy', y);

        // Fade trail
        trail.style.opacity = String(0.3 * (1 - t * 0.6));

        // Show arrowhead near end
        if (t > 0.85) {
            arrow.setAttribute('opacity', String((t - 0.85) / 0.15));
            // Arrow direction
            const ax = toPos.x, ay = toPos.y;
            // Tangent at t=1: direction from ctrl to end
            const tdx = toPos.x - ctrlX;
            const tdy = toPos.y - ctrlY;
            const tlen = Math.sqrt(tdx * tdx + tdy * tdy) || 1;
            const ux = tdx / tlen, uy = tdy / tlen;
            const sz = 5;
            const p1x = ax, p1y = ay;
            const p2x = ax - ux * sz + uy * sz * 0.5;
            const p2y = ay - uy * sz - ux * sz * 0.5;
            const p3x = ax - ux * sz - uy * sz * 0.5;
            const p3y = ay - uy * sz + ux * sz * 0.5;
            arrow.setAttribute('points', `${p1x},${p1y} ${p2x},${p2y} ${p3x},${p3y}`);
        }

        if (t < 1) {
            requestAnimationFrame(frame);
        } else {
            // Fade out and clean up
            let fadeT = 0;
            function fadeOut() {
                if (cancelled) return;
                fadeT += 0.05;
                const op = Math.max(0, 1 - fadeT);
                dot.style.opacity = String(op);
                trail.style.opacity = String(0.12 * op);
                arrow.style.opacity = String(op * 0.6);
                if (fadeT < 1) {
                    requestAnimationFrame(fadeOut);
                } else {
                    if (trail.parentNode) trail.parentNode.removeChild(trail);
                    if (dot.parentNode) dot.parentNode.removeChild(dot);
                    if (arrow.parentNode) arrow.parentNode.removeChild(arrow);
                    const idx = clusterPacketAnimations.indexOf(anim);
                    if (idx >= 0) clusterPacketAnimations.splice(idx, 1);
                }
            }
            requestAnimationFrame(fadeOut);
        }
    }
    requestAnimationFrame(frame);
}


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
                clustersData = msg.clusters || {};
                addMachineMarkers(msg.machines || []);
                addBGPVisualization(msg.bgp_peers || [], msg.my_asn, msg.my_asn_coords);
                renderClusterButtons();
                break;

            case 'flow':
                animatePacket(msg.flow);
                addFlowToList(msg.flow);
                animateClusterPacket(msg.flow);
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

    // Cluster overlay close button
    const closeBtn = document.getElementById('cluster-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeCluster);
    }

    // Cluster overlay toggle
    const clusterToggle = document.getElementById('toggle-cluster-overlay');
    if (clusterToggle) {
        clusterToggle.addEventListener('change', function(e) {
            const overlay = document.getElementById('cluster-overlay');
            if (!e.target.checked) {
                overlay.classList.add('hidden');
            } else if (activeClusterName) {
                overlay.classList.remove('hidden');
            }
        });
    }
}

// ---------------------------------------------------------------------------
// Initialize
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', function() {
    initMap();
    setupControls();
    connectWebSocket();
});