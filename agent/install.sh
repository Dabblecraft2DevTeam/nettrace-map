#!/bin/bash
#
# NetTrace Map Agent — Installation Script
# Installs the monitoring agent as a systemd service.
#
# Usage:
#   sudo ./install.sh [--server URL] [--interval SECONDS] [--name NAME] [--cluster CLUSTER]
#
set -e

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AGENT_NAME="nettrace-agent"
AGENT_DIR="/opt/nettrace-agent"
AGENT_FILE="agent.py"
SERVICE_FILE="/etc/systemd/system/${AGENT_NAME}.service"
CONFIG_FILE="/etc/nettrace-agent.conf"

# Defaults (can be overridden by CLI args)
SERVER_URL="http://localhost:8000"
INTERVAL=5
INSTANCE_NAME=""
CLUSTER_NAME=""

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------

while [[ $# -gt 0 ]]; do
    case "$1" in
        --server)   SERVER_URL="$2"; shift 2 ;;
        --interval) INTERVAL="$2"; shift 2 ;;
        --name)     INSTANCE_NAME="$2"; shift 2 ;;
        --cluster)  CLUSTER_NAME="$2"; shift 2 ;;
        --help|-h)
            echo "Usage: sudo $0 [--server URL] [--interval SECONDS] [--name NAME] [--cluster CLUSTER]"
            echo ""
            echo "Options:"
            echo "  --server URL      NetTrace backend URL (default: http://localhost:8000)"
            echo "  --interval N      Report interval in seconds (default: 5)"
            echo "  --name NAME       Instance name (default: hostname)"
            echo "  --cluster NAME    Cluster name this machine belongs to (default: unknown)"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

if [[ $EUID -ne 0 ]]; then
    echo "ERROR: This script must be run as root (use sudo)."
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 is not installed. Please install Python 3.8+ first."
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python version: ${PY_VERSION}"

# ---------------------------------------------------------------------------
# Install agent files
# ---------------------------------------------------------------------------

echo ">>> Installing NetTrace Map Agent..."

# Create agent directory
mkdir -p "${AGENT_DIR}"

# Copy agent script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cp "${SCRIPT_DIR}/${AGENT_FILE}" "${AGENT_DIR}/${AGENT_FILE}"
chmod +x "${AGENT_DIR}/${AGENT_FILE}"

echo "  Agent installed to ${AGENT_DIR}/${AGENT_FILE}"

# ---------------------------------------------------------------------------
# Write config file
# ---------------------------------------------------------------------------

echo ">>> Writing configuration to ${CONFIG_FILE}..."

cat > "${CONFIG_FILE}" << EOF
[nettrace]
server = ${SERVER_URL}
interval = ${INTERVAL}
EOF

if [[ -n "${INSTANCE_NAME}" ]]; then
    echo "instance_name = ${INSTANCE_NAME}" >> "${CONFIG_FILE}"
fi

if [[ -n "${CLUSTER_NAME}" ]]; then
    echo "cluster = ${CLUSTER_NAME}" >> "${CONFIG_FILE}"
fi

chmod 644 "${CONFIG_FILE}"

# ---------------------------------------------------------------------------
# Create systemd service
# ---------------------------------------------------------------------------

echo ">>> Creating systemd service..."

cat > "${SERVICE_FILE}" << EOF
[Unit]
Description=NetTrace Map Monitoring Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 ${AGENT_DIR}/${AGENT_FILE}
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${AGENT_NAME}

# Security hardening
NoNewPrivileges=true
ProtectSystem=full
ProtectHome=true
PrivateTmp=true
ReadWritePaths=${CONFIG_FILE}

[Install]
WantedBy=multi-user.target
EOF

echo "  Service file: ${SERVICE_FILE}"

# ---------------------------------------------------------------------------
# Enable and start service
# ---------------------------------------------------------------------------

echo ">>> Enabling and starting service..."

systemctl daemon-reload
systemctl enable "${AGENT_NAME}"
systemctl restart "${AGENT_NAME}"

# Check status
sleep 2
if systemctl is-active --quiet "${AGENT_NAME}"; then
    echo ""
    echo "✓ NetTrace Map Agent installed and running successfully!"
    echo ""
    echo "  Service:  ${AGENT_NAME}"
    echo "  Config:   ${CONFIG_FILE}"
    echo "  Logs:     journalctl -u ${AGENT_NAME} -f"
    echo "  Status:   systemctl status ${AGENT_NAME}"
    echo ""
    echo "  Server:   ${SERVER_URL}"
    echo "  Interval: ${INTERVAL}s"
else
    echo ""
    echo "⚠  Service installed but may not be running. Check logs:"
    echo "  journalctl -u ${AGENT_NAME} -n 20"
    exit 1
fi