# file: src/k3s_deploy_cli/k3s_manager.py
"""
Core class for managing K3s deployment operations.
"""
import ipaddress
import json
from typing import Any, Dict, List, Optional, Tuple

import requests  # type: ignore

from . import config as app_config
from . import proxmox_api
from .exceptions import (
    ConfigurationError,
    K3sDeployError,
    NodeDiscoveryError,
    ProxmoxError,
)
from .logging_utils import log_info_blue, log_info_green, log_info_yellow, logger
from .models import VMIdentifier


class K3sDeploymentManager:
    """
    Orchestrates K3s deployment tasks including node discovery,
    VM management, IP configuration, and K3s version checks.
    """

    def __init__(self) -> None:
        self.k3s_version: str = app_config.K3S_VERSION  # Allow modification
        self.servers: List[VMIdentifier] = []
        self.agents: List[VMIdentifier] = []
        self.storage: List[VMIdentifier] = []
        self.all_nodes: List[VMIdentifier] = []
        self.server_master: Optional[VMIdentifier] = None
        self.servers_no_first: List[VMIdentifier] = []

    def _parse_vm_location(self, location_str: str) -> Tuple[str, int]:
        """Parses "node:vmid" string into (node, vmid)."""
        if ":" not in location_str:
            raise ValueError(
                f"Invalid VM location format: '{location_str}'. Expected 'node:vmid'."
            )
        parts = location_str.split(":", 1)
        try:
            return parts[0], int(parts[1])
        except ValueError:
            raise ValueError(
                f"Invalid VMID in location: '{location_str}'. VMID must be an integer."
            )

    def _populate_node_lists(self) -> None:
        """Populates server_master and servers_no_first from self.servers."""

        sort_key = lambda vm: (vm.proxmox_node, vm.vmid)
        self.all_nodes.sort(key=sort_key)
        self.servers.sort(key=sort_key)
        self.agents.sort(key=sort_key)
        self.storage.sort(key=sort_key)
        log_info_blue(
            logger, "  Sorted discovered node lists for deterministic processing."
        )

        if self.servers:
            self.server_master = self.servers[0]
            log_info_green(logger, f"  Server master is set to: {self.server_master}")
            self.servers_no_first = self.servers[1:]
            if self.servers_no_first:
                log_info_blue(
                    logger,
                    f"  Remaining servers (excluding master): {', '.join(map(str, self.servers_no_first))}",
                )
            else:
                log_info_blue(logger, "  No other server nodes besides the master.")
        else:
            self.server_master = None
            self.servers_no_first = []
            log_info_yellow(logger, "No server entries discovered/loaded.")

        # Log discovered nodes
        if self.servers:
            log_info_green(
                logger,
                f"Discovered server entries: {', '.join(map(str, self.servers))}",
            )
        if self.agents:
            log_info_green(
                logger, f"Discovered agent entries: {', '.join(map(str, self.agents))}"
            )
        if self.storage:
            log_info_green(
                logger,
                f"Discovered storage entries: {', '.join(map(str, self.storage))}",
            )

    def load_nodes_from_config_file(self) -> bool:
        """
        Loads node information from the `config.json` file.
        Assumes 'node:vmid' format in config.json for now.
        """
        if not app_config.NODE_CONFIG_FILE.exists():
            return False

        log_info_blue(
            logger, f"Loading node information from {app_config.NODE_CONFIG_FILE}..."
        )
        try:
            with open(app_config.NODE_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            raise ConfigurationError(
                f"Failed to load or parse {app_config.NODE_CONFIG_FILE}: {e}"
            )

        loaded_servers: List[VMIdentifier] = []
        loaded_agents: List[VMIdentifier] = []
        loaded_storage: List[VMIdentifier] = []

        # Assuming structure like: {"nodes": [{"id": "pve1", "vms": [{"vmid": 100, "role": "SERVER"}]}]}
        # This matches the jq queries in the bash script fairly closely.
        for p_node_info in data.get("nodes", []):
            proxmox_node_id = p_node_info.get("id")
            if not proxmox_node_id:
                continue
            for vm_info in p_node_info.get("vms", []):
                vmid = vm_info.get("vmid")
                role = str(vm_info.get("role", "")).upper()
                if not vmid:
                    continue

                vm_identifier = VMIdentifier(proxmox_node=proxmox_node_id, vmid=vmid)
                # For now, config file does not provide name or other details directly for VMIdentifier
                # We might need to fetch them if needed for other operations based on config loaded nodes

                if (
                    role == app_config.SERVER_TAG.upper() or role == "SERVER"
                ):  # "SERVER" for simpler JSON
                    loaded_servers.append(vm_identifier)
                elif role == app_config.AGENT_TAG.upper() or role == "AGENT":
                    loaded_agents.append(vm_identifier)
                elif role == app_config.STORAGE_TAG.upper() or role == "STORAGE":
                    loaded_storage.append(vm_identifier)

        self.servers = loaded_servers
        self.agents = loaded_agents
        self.storage = loaded_storage
        self.all_nodes = list(
            set(self.servers + self.agents + self.storage)
        )  # Unique list

        log_info_green(
            logger,
            f"Found {len(self.servers)} server(s), {len(self.agents)} agent(s), "
            f"and {len(self.storage)} storage node(s) from config file.",
        )
        self._populate_node_lists()
        return True

    def discover_nodes_by_tags(self) -> None:
        """
        Discovers K3s nodes based on Proxmox tags.
        Populates self.servers, self.agents, self.storage, self.all_nodes.
        """
        log_info_blue(logger, "Discovering K3s nodes based on Proxmox tags...")
        # Initialize lists
        discovered_servers: List[VMIdentifier] = []
        discovered_agents: List[VMIdentifier] = []
        discovered_storage: List[VMIdentifier] = []
        discovered_all_nodes: List[VMIdentifier] = []

        try:
            proxmox_host_nodes = proxmox_api.get_proxmox_cluster_nodes()
        except ProxmoxError as e:
            raise NodeDiscoveryError(f"Failed to get Proxmox host nodes: {e}")

        if not proxmox_host_nodes:
            raise NodeDiscoveryError(
                "No Proxmox host nodes found. Cannot discover VMs by tags."
            )

        for p_node_name in proxmox_host_nodes:
            try:
                vmids_on_node = proxmox_api.get_vms_on_node(p_node_name)
            except ProxmoxError:  # Logged in proxmox_api, continue to next node
                continue

            for vmid in vmids_on_node:
                try:
                    vm_config = proxmox_api.get_vm_config(p_node_name, vmid)
                except ProxmoxError:  # Logged, skip this VM
                    continue

                vm_name = vm_config.get("name")
                tags_str: str = vm_config.get(
                    "tags", ""
                )  # Tags are semicolon-separated
                vm_tags: List[str] = [
                    tag.strip() for tag in tags_str.split(";") if tag.strip()
                ]

                if not vm_tags:
                    continue

                vm_identifier = VMIdentifier(
                    proxmox_node=p_node_name,
                    vmid=vmid,
                    name=vm_name,
                    tags=vm_tags,
                    config=vm_config,
                )

                is_server, is_agent, is_storage = False, False, False
                if app_config.SERVER_TAG in vm_tags:
                    is_server = True
                if app_config.AGENT_TAG in vm_tags:
                    is_agent = True
                if app_config.STORAGE_TAG in vm_tags:
                    is_storage = True

                if not (is_server or is_agent or is_storage):
                    # log_info_blue(logger, f"      VM {vm_identifier} does not have a K3s role tag. Skipping.")
                    continue

                log_info_green(
                    logger,
                    f"      Found VM: {vm_identifier} with tags: {', '.join(vm_tags)}",
                )
                self.all_nodes.append(vm_identifier)
                if is_server:
                    self.servers.append(vm_identifier)
                    log_info_green(
                        logger, f"      Discovered K3s server: {vm_identifier}"
                    )
                if is_agent:
                    self.agents.append(vm_identifier)
                    log_info_green(
                        logger, f"      Discovered K3s agent: {vm_identifier}"
                    )
                if is_storage:
                    self.storage.append(vm_identifier)
                    log_info_green(
                        logger, f"      Discovered K3s storage: {vm_identifier}"
                    )

        # Remove duplicates that might occur if a VM has multiple role tags (unlikely but possible)
        self.all_nodes = list(set(self.all_nodes))
        self.servers = list(set(self.servers))
        self.agents = list(set(self.agents))
        self.storage = list(set(self.storage))

        if not self.all_nodes:
            log_info_yellow(
                logger,
                "Warning: No K3s nodes discovered with any of the role tags "
                f"({app_config.SERVER_TAG}, {app_config.AGENT_TAG}, {app_config.STORAGE_TAG}).",
            )
            # Not raising an error here, let the caller decide.

        self._populate_node_lists()

    def ensure_nodes_are_discovered(self, discover_if_empty: bool = True) -> None:
        """
        Ensures node lists are populated, either from config file or by discovery.
        Raises NodeDiscoveryError if no nodes are found after trying.
        """
        if self.all_nodes:  # Already populated
            return

        if self.load_nodes_from_config_file():
            if self.all_nodes:
                return
            else:  # Config file exists but no relevant nodes found
                log_info_yellow(
                    logger,
                    f"Config file {app_config.NODE_CONFIG_FILE} loaded but no K3s nodes defined.",
                )

        if discover_if_empty:
            log_info_blue(
                logger,
                f"{app_config.NODE_CONFIG_FILE} not found or empty. Attempting tag-based discovery...",
            )
            self.discover_nodes_by_tags()
            if self.all_nodes:
                return

        # If still no nodes
        raise NodeDiscoveryError(
            "Failed to discover any nodes via tags and config.json not found or empty. "
            "Aborting operation that requires nodes."
        )

    def check_k3s_version(self, ask_update: bool = False) -> None:
        """
        Checks the current K3s version against the latest release on GitHub.
        Optionally asks the user if they want to update the version used by the script.
        """
        log_info_blue(logger, "Checking current K3s version against latest release...")
        try:
            response = requests.get(app_config.K3S_RELEASES_URL, timeout=10)
            response.raise_for_status()
            latest_release_data = response.json()
            latest_tag_name = latest_release_data.get("tag_name")

            if not latest_tag_name:
                log_info_yellow(
                    logger,
                    "Warning: Could not determine latest K3s version from GitHub API response.",
                )
                return

            log_info_blue(
                logger, f"  Current K3s version configured: {self.k3s_version}"
            )
            log_info_blue(logger, f"  Latest K3s release on GitHub: {latest_tag_name}")

            if self.k3s_version != latest_tag_name:
                log_info_yellow(
                    logger,
                    f"  Info: Current K3s version {self.k3s_version} differs from latest release {latest_tag_name}.",
                )
                if ask_update:
                    answer = (
                        input(
                            f"Do you want to use the latest K3s version ({latest_tag_name})? (y/n): "
                        )
                        .strip()
                        .lower()
                    )
                    if answer == "y":
                        self.k3s_version = latest_tag_name
                        app_config.K3S_VERSION = latest_tag_name  # Update global config if desired, or manage state better
                        log_info_green(
                            logger,
                            f"Updated to use latest K3s version: {self.k3s_version}",
                        )
                    else:
                        log_info_blue(
                            logger,
                            f"Continuing with current version: {self.k3s_version}",
                        )
            else:
                log_info_green(logger, f"Using latest K3s version: {self.k3s_version}")

        except requests.RequestException as e:
            log_info_yellow(logger, f"Warning: Failed to fetch latest K3s version: {e}")
        except json.JSONDecodeError:
            log_info_yellow(
                logger, "Warning: Failed to parse K3s version from GitHub API response."
            )

    def perform_vm_action(self, action: str) -> None:
        """
        Performs a power action (start, stop, restart) on all discovered K3s VMs.
        'stop' implies graceful shutdown.
        """
        self.ensure_nodes_are_discovered()
        log_info_blue(
            logger, f"Performing Proxmox VM action '{action}' on discovered K3s VMs..."
        )

        if not self.all_nodes:
            log_info_yellow(
                logger,
                f"Warning: No VM locations discovered/loaded. Skipping Proxmox VM action '{action}'.",
            )
            return

        for vm in self.all_nodes:
            log_info_blue(logger, f"  Processing {vm} for action '{action}'...")
            try:
                status_data = proxmox_api.get_vm_status(vm.proxmox_node, vm.vmid)
                current_status = status_data.get("status", "unknown").lower()
                # Store status for later use
                vm.status = current_status
            except ProxmoxError as e:
                logger.error(
                    f"    Could not get status for {vm}. Skipping action. Error: {e}"
                )
                continue

            if action == "start":
                if current_status == "running":
                    log_info_green(logger, f"    VM {vm} is already running.")
                else:
                    log_info_blue(
                        logger,
                        f"    VM {vm} is currently '{current_status}'. Attempting to start...",
                    )
                    proxmox_api.control_vm(vm.proxmox_node, vm.vmid, "start")
            elif action == "stop":  # Graceful shutdown
                if current_status == "stopped":
                    log_info_green(logger, f"    VM {vm} is already stopped.")
                else:
                    log_info_blue(
                        logger,
                        f"    VM {vm} is currently '{current_status}'. Attempting graceful shutdown...",
                    )
                    proxmox_api.control_vm(
                        vm.proxmox_node, vm.vmid, "stop"
                    )  # 'stop' maps to 'shutdown' in control_vm
            elif action == "restart":
                if current_status != "running":
                    log_info_yellow(
                        logger,
                        f"    VM {vm} is not running (status: '{current_status}'). Starting it instead of rebooting.",
                    )
                    # Alternative: skip or error. Bash script started it.
                    proxmox_api.control_vm(vm.proxmox_node, vm.vmid, "start")
                else:
                    log_info_blue(
                        logger,
                        f"    VM {vm} is currently 'running'. Attempting to reboot...",
                    )
                    proxmox_api.control_vm(vm.proxmox_node, vm.vmid, "reboot")
            else:
                logger.error(f"Internal error: Unknown VM action '{action}' requested.")

    def _get_ssh_public_key(self) -> Optional[str]:
        """
        Resolves the SSH public key from various sources in order of priority:
        1. Environment variable K3S_SSH_PUBLIC_KEY (direct key content)
        2. Config.json if it contains ssh_key field
        3. File specified by SSH_PUBLIC_KEY_PATH

        Returns:
            The SSH public key content, or None if no key could be found or resolved
        """
        # Check for direct key content from environment
        if app_config.SSH_PUBLIC_KEY:
            log_info_blue(
                logger,
                "Using SSH public key from K3S_SSH_PUBLIC_KEY environment variable",
            )
            return app_config.SSH_PUBLIC_KEY

        # Check if config.json exists and has a ssh_key field
        if app_config.NODE_CONFIG_FILE.exists():
            try:
                with open(app_config.NODE_CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "ssh_key" in data:
                        log_info_blue(
                            logger,
                            f"Using SSH public key from {app_config.NODE_CONFIG_FILE}",
                        )
                        return data["ssh_key"]
            except (json.JSONDecodeError, IOError) as e:
                log_info_yellow(
                    logger, f"Warning: Could not read SSH key from config file: {e}"
                )

        # Finally, try to read key from file
        if app_config.SSH_PUBLIC_KEY_PATH.exists():
            try:
                with open(app_config.SSH_PUBLIC_KEY_PATH, "r", encoding="utf-8") as f:
                    key_content = f.read().strip()
                    if key_content:
                        log_info_blue(
                            logger,
                            f"Using SSH public key from {app_config.SSH_PUBLIC_KEY_PATH}",
                        )
                        return key_content
                    else:
                        log_info_yellow(
                            logger,
                            f"Warning: SSH key file {app_config.SSH_PUBLIC_KEY_PATH} is empty",
                        )
            except IOError as e:
                log_info_yellow(logger, f"Warning: Failed to read SSH key file: {e}")
        else:
            log_info_yellow(
                logger,
                f"SSH key file {app_config.SSH_PUBLIC_KEY_PATH} does not exist. "
                f"SSH key deployment will be skipped.",
            )

        return None

    def configure_vms(self, restart_after: bool = False, force: bool = False) -> None:
        """
        Configures VMs with static IPs and SSH keys using cloud-init.

        Args:
            restart_after: If True, restarts VMs after configuration is applied
                          to apply cloud-init changes
            force: If True, updates cloud-init configuration even if no changes are detected
        """
        self.ensure_nodes_are_discovered()
        log_info_blue(
            logger,
            "Starting VM configuration (IPs and SSH keys) for VMs with K3s role tags",
        )

        if not self.all_nodes:
            log_info_yellow(
                logger,
                "Warning: No VM locations discovered/loaded. Skipping VM configuration.",
            )
            return

        # Get SSH public key
        ssh_key = self._get_ssh_public_key()
        if not ssh_key:
            log_info_yellow(
                logger,
                "No SSH public key found. VM configuration will only include network settings.",
            )

        # Track which VMs were modified and need restart
        modified_vms: List[VMIdentifier] = []
        # Track running VMs that need restart (only used for messaging)
        running_modified_vms: List[VMIdentifier] = []

        try:
            ip_range_start_obj = ipaddress.IPv4Address(
                app_config.K3S_NODE_IP_RANGE_START
            )
            ip_range_end_obj = ipaddress.IPv4Address(app_config.K3S_NODE_IP_RANGE_END)
        except ipaddress.AddressValueError as e:
            raise ConfigurationError(f"Invalid IP address in range configuration: {e}")

        next_ip_to_assign_int = int(ip_range_start_obj)
        ip_range_end_int = int(ip_range_end_obj)

        # Sort nodes to ensure consistent IP assignment if discovery order changes
        # Sorting by proxmox_node then vmid
        sorted_nodes = sorted(self.all_nodes, key=lambda vm: (vm.proxmox_node, vm.vmid))

        for vm in sorted_nodes:
            log_info_blue(logger, f"  Processing {vm} for IP configuration...")

            # First get VM status to know if it's running
            try:
                status_data = proxmox_api.get_vm_status(vm.proxmox_node, vm.vmid)
                current_status = status_data.get("status", "unknown").lower()
                vm.status = current_status  # Store status for later use
            except ProxmoxError:
                logger.warning(f"    Could not get status for {vm}. Assuming unknown.")
                vm.status = "unknown"

            # Fetch full VM config if not already populated (e.g., if loaded from basic config.json)
            if (
                not vm.config
                or f"ipconfig{app_config.K3S_NODE_IPCONFIG_INDEX}" not in vm.config
            ):
                try:
                    vm.config = proxmox_api.get_vm_config(vm.proxmox_node, vm.vmid)
                    vm.name = vm.config.get("name", vm.name)  # Update name if available
                except ProxmoxError as e:
                    logger.error(
                        f"    Could not get config for {vm} to check current IP. Skipping. Error: {e}"
                    )
                    continue

            if next_ip_to_assign_int > ip_range_end_int:
                logger.error(
                    f"      Error: No more IP addresses available in the range "
                    f"{app_config.K3S_NODE_IP_RANGE_START} - {app_config.K3S_NODE_IP_RANGE_END}."
                )
                logger.error(
                    f"      Cannot configure {vm}. Please expand the range or check assignments."
                )
                continue  # Or raise error to stop entire process

            current_ip_to_assign = str(ipaddress.IPv4Address(next_ip_to_assign_int))
            target_ipconfig_value = (
                f"ip={current_ip_to_assign}/{app_config.K3S_NODE_CIDR},"
                f"gw={app_config.K3S_NODE_GATEWAY}"
            )
            target_nameserver_value = " ".join(
                app_config.K3S_NODE_DNS_SERVERS
            )  # Space-separated for pvesh
            target_searchdomain_value = app_config.K3S_NODE_SEARCH_DOMAIN

            # Idempotency Check
            current_ipconfig_key = f"ipconfig{app_config.K3S_NODE_IPCONFIG_INDEX}"
            current_ipconfig_value = vm.config.get(current_ipconfig_key, "")
            current_nameserver_value = vm.config.get("nameserver", "")
            current_searchdomain_value = vm.config.get("searchdomain", "")

            needs_update = (
                force  # If force is True, we'll update regardless of current config
            )
            if not needs_update:  # Only check for changes if not forcing update
                if current_ipconfig_value != target_ipconfig_value:
                    needs_update = True
                if (
                    target_nameserver_value
                    and current_nameserver_value != target_nameserver_value
                ):
                    needs_update = True
                if (
                    target_searchdomain_value
                    and current_searchdomain_value != target_searchdomain_value
                ):
                    needs_update = True

            vm_display_name = vm.name if vm.name else f"VMID {vm.vmid}"

            if not needs_update:
                log_info_green(
                    logger,
                    f"      {vm_display_name} on {vm.proxmox_node} is already configured with IP: "
                    f"{current_ip_to_assign}. Skipping.",
                )
                next_ip_to_assign_int += 1
                continue

            log_info_blue(
                logger,
                f"      Preparing to assign IP: {current_ip_to_assign}/{app_config.K3S_NODE_CIDR}, "
                f"GW: {app_config.K3S_NODE_GATEWAY}, DNS: {target_nameserver_value} "
                f"to {vm_display_name}",
            )
            if target_searchdomain_value:
                log_info_blue(
                    logger, f"      Adding search domain: {target_searchdomain_value}"
                )

            try:
                proxmox_api.set_vm_network_config(
                    vm.proxmox_node,
                    vm.vmid,
                    target_ipconfig_value,
                    target_nameserver_value,
                    target_searchdomain_value,
                    ssh_key,  # Pass SSH key to the API function
                )
                modified_vms.append(vm)

                # Only add running VMs to the list for restart messages
                if vm.status == "running":
                    running_modified_vms.append(vm)

                    # Only show the individual reboot message for running VMs when not auto-restarting
                    if not restart_after:
                        log_info_yellow(
                            logger,
                            f"      Note: {vm_display_name} needs a reboot for cloud-init to apply these settings.",
                        )
            except ProxmoxError as e:  # Already logged in proxmox_api
                logger.error(
                    f"      Skipping IP configuration for {vm_display_name} due to previous error."
                )
                # Decide if we should stop or try to assign next IP to next VM
                # For now, we continue, but this IP is "lost" for this run.
                # To be robust, one might reserve this IP or retry.

            next_ip_to_assign_int += 1

        # Display summary of modified VMs that need restart (only for running VMs, and when not auto-restarting)
        if running_modified_vms and not restart_after:
            modified_vm_names = [
                vm.name if vm.name else f"VMID {vm.vmid}" for vm in running_modified_vms
            ]
            log_info_yellow(
                logger,
                f"The following running VMs were modified and need restart for cloud-init changes to apply: "
                f"{', '.join(modified_vm_names)}",
            )

        # Restart VMs if requested
        if modified_vms and restart_after:
            log_info_blue(logger, "Restarting modified VMs as requested...")
            for vm in modified_vms:
                log_info_blue(logger, f"  Restarting VM {vm}...")
                try:
                    proxmox_api.control_vm(vm.proxmox_node, vm.vmid, "restart")
                    log_info_green(logger, f"    Successfully restarted VM {vm}")
                except ProxmoxError as e:
                    logger.error(f"    Failed to restart VM {vm}. Error: {e}")

        log_info_green(logger, "VM configuration process completed.")

    def provision_k3s_cluster(self) -> None:
        """
        Placeholder for K3s cluster provisioning logic.
        """
        self.ensure_nodes_are_discovered()
        log_info_green(logger, "STARTING K3S PROVISIONING")

        if not self.server_master:
            logger.error(
                "Error: No K3s server master node defined or discovered for provisioning. Aborting K3s setup."
            )
            raise K3sDeployError("Cannot provision K3s: No master server found.")

        log_info_blue(
            logger,
            "IMPORTANT: This section assumes SERVERS, AGENTS, and STORAGE lists contain "
            "nodes that are reachable and correctly configured (e.g., via IP addresses).",
        )
        log_info_blue(
            logger, f"Current SERVER_MASTER (first master target): {self.server_master}"
        )
        if self.servers_no_first:
            log_info_blue(
                logger,
                f"Other server nodes: {', '.join(map(str, self.servers_no_first))}",
            )
        if self.agents:
            log_info_blue(logger, f"Agent nodes: {', '.join(map(str, self.agents))}")

        # --- Begin K3s Provisioning Logic ---
        # This is where you'd implement SSH connections, k3s installation commands, etc.
        # For example:
        # 1. Install K3s on self.server_master
        #    - SSH to server_master.ip_address (needs IP to be known)
        #    - Construct K3S_URL, INSTALL_K3S_EXEC based on config
        #    - Handle token retrieval
        # 2. Install K3s on self.servers_no_first (other masters)
        # 3. Install K3s on self.agents
        # 4. Configure storage if self.storage nodes exist and are used for something like Longhorn.
        #
        # This part is highly dependent on your exact provisioning strategy (ansible, direct SSH, etc.)
        # and how VMs get their IPs (DHCP then discover, or static via configure-ips).
        # The bash script stores "node:vmid" or IPs. For provisioning, actual IPs are crucial.
        # The `configure-ips` step *should* set IPs that cloud-init applies.
        # A further
