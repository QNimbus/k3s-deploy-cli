# file: src/k3s_deploy_cli/models.py
"""Data models for the K3s deployment tool."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

@dataclass
class VMIdentifier:
    """
    Represents a Proxmox VM with its location and role tags.
    """
    proxmox_node: str
    vmid: int
    name: Optional[str] = None
    ip_address: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict) # Store raw VM config if needed

    def __str__(self) -> str:
        return f"{self.proxmox_node}:{self.vmid}" + (f" ({self.name})" if self.name else "")

    def __hash__(self) -> int:
        return hash((self.proxmox_node, self.vmid))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VMIdentifier):
            return NotImplemented
        return (self.proxmox_node, self.vmid) == (other.proxmox_node, other.vmid)

@dataclass
class ProxmoxNode:
    """Represents a Proxmox physical node."""
    name: str
    vms: List[VMIdentifier] = field(default_factory=list)