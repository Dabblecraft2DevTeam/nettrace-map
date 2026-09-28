#!/bin/bash
#
# NetTrace Map Agent — Uninstallation Script
# Stops and removes the monitoring agent and systemd service.
#
set -e

AGENT_NAME="nettrace-agent"
AGENT_DIR="/opt/nettrace-agent"
SERVICE_FILE="/etc/systemd/system/${AGENT_NAME}.service"
CONFIG_FILE="/etc/nettrace-agent.conf"

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

if [[ $EUID -ne 0 ]]; then
    echo "ERROR: This script must be run as root (use sudo)."
    exit 1
fi

echo ">>> Uninstalling NetTrace Map Agent..."

# ---------------------------------------------------------------------------
# Stop and disable service
# ---------------------------------------------------------------------------

if systemctl is-active --quiet "${AGENT_NAME}" 2>/dev/null; then
    systemctl stop "${AGENT_NAME}"
    echo "  Service stopped."
else
    echo "  Service was not running."
fi

if systemctl is-enabled --quiet "${AGENT_NAME}" 2>/dev/null; then
    systemctl disable "${AGENT_NAME}"
    echo "  Service disabled."
fi

# ---------------------------------------------------------------------------
# Remove files
# ---------------------------------------------------------------------------

if [[ -f "${SERVICE_FILE}" ]]; then
    rm -f "${SERVICE_FILE}"
    echo "  Removed: ${SERVICE_FILE}"
fi

systemctl daemon-reload

if [[ -f "${CONFIG_FILE}" ]]; then
    rm -f "${CONFIG_FILE}"
    echo "  Removed: ${CONFIG_FILE}"
fi

if [[ -d "${AGENT_DIR}" ]]; then
    rm -rf "${AGENT_DIR}"
    echo "  Removed: ${AGENT_DIR}"
fi

echo ""
echo "✓ NetTrace Map Agent uninstalled successfully."
echo ""
echo "  Note: If you installed psutil separately, it remains installed."
echo "  To remove it: pip3 uninstall psutil  (or apt remove python3-psutil)"