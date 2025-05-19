# file: src/k3s_deploy_cli/config.py
"""Configuration constants for the K3s deployment tool."""

import os
from pathlib import Path
from typing import List, Optional

# Proxmox API Connection Details (to be sourced from environment variables)
PROXMOX_HOST: Optional[str] = os.environ.get("PROXMOX_HOST")
PROXMOX_PORT: int = int(os.environ.get("PROXMOX_PORT", "8006"))
PROXMOX_USER: Optional[str] = os.environ.get("PROXMOX_USER")
PROXMOX_PASSWORD: Optional[str] = os.environ.get("PROXMOX_PASSWORD")
PROXMOX_TOKEN_ID: Optional[str] = os.environ.get("PROXMOX_API_TOKEN_ID")
PROXMOX_TOKEN_SECRET: Optional[str] = os.environ.get("PROXMOX_API_TOKEN_SECRET")
# SSL verification for Proxmox API. Set to "0" or "false" to disable (not recommended for production).
PROXMOX_SSL_VERIFY: bool = os.environ.get("PROXMOX_SSL_VERIFY", "true").lower() not in (
    "0",
    "false",
)


# Base dir
ROOTDIR: Path = Path(os.environ.get("K3S_DEPLOY_ROOTDIR", Path.home() / "k3s-deploy"))

# Kube-VIP version
KUBE_VIP_VERSION: str = "v0.9.1"

# k3s Version (can be updated by check_version)
K3S_VERSION: str = "v1.32.4+k3s1"

# Tags for identifying different node types
SERVER_TAG: str = "k3s-server"
AGENT_TAG: str = "k3s-agent"
STORAGE_TAG: str = "k3s-storage"

# K3s Node Network Configuration (for cloud-init)
K3S_NODE_IP_RANGE_START: str = "10.10.0.201"
K3S_NODE_IP_RANGE_END: str = "10.10.0.229"
K3S_NODE_CIDR: str = "24"
K3S_NODE_GATEWAY: str = "10.10.0.1"
K3S_NODE_DNS_SERVERS: List[str] = ["10.10.0.1"]  # List of DNS servers
K3S_NODE_SEARCH_DOMAIN: Optional[str] = "lan.home.vwn.io"
K3S_NODE_IPCONFIG_INDEX: int = 0

# User of remote machines (for SSH, not used in current pvesh interactions)
REMOTE_USER: str = "ubuntu"

# Interface used on remotes (for SSH, not used in current pvesh interactions)
REMOTE_INTERFACE: str = "eth0"

# Set the virtual IP address (VIP)
VIP_ADDRESS: str = "10.10.0.150"

# Loadbalancer IP range
LOADBALANCER_IP_RANGE: str = "10.10.0.151-10.10.0.199"

# SSH certificate name variable (for SSH, not used in current pvesh interactions)
SSH_CERT_NAME: str = "id_rsa"

# SSH config file (for SSH, not used in current pvesh interactions)
SSH_CONFIG_FILE: Path = Path.home() / ".ssh" / "config"

# SSH public key for VM configuration via cloud-init
# Can be provided as direct key content or path to key file
SSH_PUBLIC_KEY: Optional[str] = os.environ.get("K3S_SSH_PUBLIC_KEY")
SSH_PUBLIC_KEY_PATH: Path = Path(
    os.environ.get("K3S_SSH_PUBLIC_KEY_PATH", str(Path.home() / ".ssh" / "id_rsa.pub"))
)

# Path to the local config.json file
NODE_CONFIG_FILE: Path = Path("./config.json")

# GitHub API URL for K3s releases
K3S_RELEASES_URL: str = "https://api.github.com/repos/k3s-io/k3s/releases/latest"
