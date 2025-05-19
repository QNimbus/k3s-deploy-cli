# file: src/k3s_deploy_cli/proxmox_api.py
"""
Functions for interacting with the Proxmox API via the proxmoxer library.
"""
from typing import Any, Dict, List, Optional

from proxmoxer import ProxmoxAPI  # type: ignore
from proxmoxer.core import ResourceException  # type: ignore

from . import config as app_config
from .exceptions import ConfigurationError, ProxmoxError
from .logging_utils import log_info_blue, log_info_green, log_info_yellow, logger

# Global ProxmoxAPI client instance
_proxmox_client: Optional[ProxmoxAPI] = None


def get_proxmox_client() -> ProxmoxAPI:
    """
    Initializes and returns a ProxmoxAPI client.
    Reads connection details from app_config (sourced from environment variables).

    Returns:
        An initialized ProxmoxAPI client.

    Raises:
        ConfigurationError: If required Proxmox connection details are missing.
        ProxmoxError: If connection to Proxmox fails.
    """
    global _proxmox_client
    if _proxmox_client:
        return _proxmox_client

    host = app_config.PROXMOX_HOST
    user_full = app_config.PROXMOX_USER
    password = app_config.PROXMOX_PASSWORD
    token_id = app_config.PROXMOX_TOKEN_ID
    token_secret = app_config.PROXMOX_TOKEN_SECRET
    ssl_verify = app_config.PROXMOX_SSL_VERIFY
    port = app_config.PROXMOX_PORT

    if not host or not user_full:
        raise ConfigurationError(
            "Proxmox host (PROXMOX_HOST) and user (PROXMOX_USER) must be set "
            "in environment variables."
        )

    temp_client: Optional[ProxmoxAPI] = None

    try:
        if token_id and token_secret:
            log_info_blue(
                logger,
                f"Attempting Proxmox API connection to {host}:{port} using API token.",
            )

            # user_full for token auth should be 'user@realm'
            # token_id is just the name of the token (e.g., 'mytoken')
            # Proxmoxer constructs 'user@realm!tokenid' internally for the 'userid' field.
            # However, the 'user' param to ProxmoxAPI for token auth IS 'user@realm!tokenid'
            api_user_string = f"{user_full}!{token_id}"
            log_info_blue(
                logger, f"Using Proxmox token user string: '{api_user_string}'."
            )

            temp_client = ProxmoxAPI(
                host,
                user=api_user_string,
                token_value=token_secret,
                port=port,
                verify_ssl=ssl_verify,
            )

        elif password:
            log_info_blue(
                logger,
                f"Attempting Proxmox API connection to {host}:{port} using password for user '{user_full}'.",
            )

            if "@" not in user_full:
                log_info_yellow(
                    logger,
                    f"PROXMOX_USER '{user_full}' does not specify a realm (e.g., @pam, @pve). "
                    "Proxmoxer will attempt to infer or use a default backend. "
                    "Authentication might fail. Please use 'username@realm' format.",
                )

            # Let Proxmoxer infer the backend from the user_full string (e.g., root@pam)
            # No explicit 'backend' parameter is passed here.
            temp_client = ProxmoxAPI(
                host,
                user=user_full,  # Pass the full 'username@realm' string
                password=password,
                port=port,
                # backend=selected_backend, # REMOVED - Let proxmoxer infer
                verify_ssl=ssl_verify,
            )
        else:
            raise ConfigurationError(
                "Either Proxmox password (PROXMOX_PASSWORD) or API token "
                "(PROXMOX_API_TOKEN_ID, PROXMOX_API_TOKEN_SECRET) must be set."
            )

        log_info_blue(
            logger,
            "ProxmoxAPI client instantiated. Verifying connection with version check...",
        )
        version_info = temp_client.version.get()
        log_info_green(
            logger,
            f"Successfully connected to Proxmox API on {host}:{port}. Version: {version_info.get('version')}",
        )
        _proxmox_client = temp_client

    except ConfigurationError:
        raise
    except ResourceException as e:
        error_content = e.content if hasattr(e, "content") and e.content else str(e)
        if (
            isinstance(error_content, dict)
            and "data" in error_content
            and error_content["data"] is None
        ):
            if e.status_code == 401:  # Unauthorized
                error_content = "Authentication failed. Please check credentials, user realm, and token permissions."
            else:
                error_content = f"API call failed with status {e.status_code}, no specific data returned."
        # This is an error from an API call (like version.get) AFTER successful instantiation
        log_info_yellow(logger, f"Proxmox API call failed: {error_content}")
        raise ProxmoxError(
            f"Proxmox API call error for {host}:{port}. Error: {error_content}"
        ) from e
    except Exception as e:
        # This is an error during ProxmoxAPI instantiation itself
        log_info_yellow(
            logger, f"Failed to initialize or connect with ProxmoxAPI client: {str(e)}"
        )
        raise ProxmoxError(
            f"Failed to establish connection with Proxmox API at {host}:{port}. Root cause: {str(e)}"
        ) from e

    if not ssl_verify and _proxmox_client:
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        log_info_yellow(
            logger,
            "Warning: SSL verification for Proxmox API is disabled. InsecureRequestWarning suppressed.",
        )

    if not _proxmox_client:
        # This safeguard should ideally not be hit if exceptions are handled correctly above
        raise ProxmoxError(
            "Proxmox client could not be initialized for an unknown reason after attempting connection."
        )
    return _proxmox_client


def get_proxmox_cluster_nodes() -> List[str]:
    """Fetches a list of Proxmox cluster node names."""
    log_info_blue(logger, "  Fetching Proxmox cluster nodes...")
    client = get_proxmox_client()
    try:
        nodes_data = client.nodes.get()
        node_names = sorted(
            [node_info["node"] for node_info in nodes_data if "node" in node_info]
        )

        if not node_names:
            log_info_yellow(logger, "  No Proxmox nodes found or data was invalid.")
            return []

        log_info_green(logger, f"  Discovered Proxmox nodes: {', '.join(node_names)}")
        return node_names
    except ResourceException as e:
        logger.error(
            f"  Failed to get Proxmox nodes: {e.content if hasattr(e, 'content') and e.content else str(e)}"
        )
        raise ProxmoxError("Could not fetch Proxmox cluster nodes.") from e


def get_vms_on_node(node_name: str) -> List[int]:
    """Fetches a list of VMIDs on a specific Proxmox node."""
    log_info_blue(logger, f"  Fetching VMs on node '{node_name}'...")
    client = get_proxmox_client()
    try:
        vms_data = client.nodes(node_name).qemu.get()
        if not vms_data:
            log_info_blue(logger, f"    No VMs found on node '{node_name}'.")
            return []

        vmids = sorted([vm_info["vmid"] for vm_info in vms_data if "vmid" in vm_info])

        if not vmids:
            log_info_blue(logger, f"    No VMIDs extracted on node '{node_name}'.")
            return []

        log_info_green(
            logger,
            f"    Discovered VMs on node '{node_name}': {', '.join(map(str, vmids))}",
        )
        return vmids
    except ResourceException as e:
        error_detail = e.content if hasattr(e, "content") and e.content else str(e)
        log_info_yellow(
            logger,
            f"    Warning: Failed to get VMs for node '{node_name}'. Node may be unreachable or API error occurred. Detail: {error_detail}",
        )
        return []  # Continue to allow discovery of other nodes


def get_vm_config(node_name: str, vmid: int) -> Dict[str, Any]:
    """Fetches the configuration for a specific VM."""
    log_info_blue(
        logger, f"    Fetching config for VM '{vmid}' on node '{node_name}'..."
    )
    client = get_proxmox_client()
    try:
        config_data = client.nodes(node_name).qemu(vmid).config.get()
        return config_data
    except ResourceException as e:
        logger.error(
            f"      Failed to get config for VM {vmid} on {node_name}: {e.content if hasattr(e, 'content') and e.content else str(e)}"
        )
        raise ProxmoxError(
            f"Could not fetch config for VM {vmid} on {node_name}."
        ) from e


def get_vm_status(node_name: str, vmid: int) -> Dict[str, Any]:
    """Fetches the current status of a specific VM."""
    log_info_blue(logger, f"  Fetching status for VM {vmid} on {node_name}...")
    client = get_proxmox_client()
    try:
        status_data = client.nodes(node_name).qemu(vmid).status.current.get()
        return status_data
    except ResourceException as e:
        logger.error(
            f"    Failed to get status for VM {vmid} on {node_name}: {e.content if hasattr(e, 'content') and e.content else str(e)}"
        )
        raise ProxmoxError(
            f"Could not fetch status for VM {vmid} on {node_name}."
        ) from e


def control_vm(node_name: str, vmid: int, action: str) -> str:
    """
    Controls a VM (start, stop, shutdown, reboot).
    'stop' action is mapped to graceful 'shutdown'.
    """
    log_info_blue(logger, f"  Attempting to {action} VM {vmid} on {node_name}...")
    client = get_proxmox_client()

    valid_actions = {"start", "stop", "shutdown", "reboot"}
    if action not in valid_actions:
        raise ValueError(f"Invalid VM action: {action}. Must be one of {valid_actions}")

    pve_api_action = action
    if action == "stop":  # Our script's "stop" means graceful shutdown
        pve_api_action = "shutdown"

    try:
        task_id = getattr(
            client.nodes(node_name).qemu(vmid).status, pve_api_action
        ).post()
        log_info_green(
            logger,
            f"    Successfully initiated {pve_api_action} for VM {vmid} on {node_name}. Task ID: {task_id}",
        )
        return task_id
    except ResourceException as e:
        logger.error(
            f"    Failed to {action} VM {vmid} on {node_name}: {e.content if hasattr(e, 'content') and e.content else str(e)}"
        )
        raise ProxmoxError(f"Could not {action} VM {vmid} on {node_name}.") from e
    except AttributeError:
        logger.error(
            f"    Invalid Proxmox API action '{pve_api_action}' derived from '{action}'."
        )
        raise ProxmoxError(f"Invalid API action for VM {vmid} on {node_name}.")


def set_vm_network_config(
    node_name: str,
    vmid: int,
    ipconfig_value: str,
    nameserver_value: Optional[str],
    searchdomain_value: Optional[str],
    ssh_key: Optional[str] = None,
) -> str:
    """
    Sets the network and SSH configuration for a VM using cloud-init parameters.

    Args:
        node_name: The name of the Proxmox node hosting the VM
        vmid: The VM ID to configure
        ipconfig_value: The ipconfig string (e.g., "ip=10.10.0.201/24,gw=10.10.0.1")
        nameserver_value: DNS servers (optional)
        searchdomain_value: Search domain (optional)
        ssh_key: SSH public key to add to the VM (optional)

    Returns:
        The result from the Proxmox API call
    """
    log_info_blue(logger, f"    Configuring VM {vmid} on {node_name}...")
    client = get_proxmox_client()

    params_to_set: Dict[str, Any] = {}
    params_to_set[f"ipconfig{app_config.K3S_NODE_IPCONFIG_INDEX}"] = ipconfig_value
    if nameserver_value:
        params_to_set["nameserver"] = nameserver_value
    if searchdomain_value:
        params_to_set["searchdomain"] = searchdomain_value
    if ssh_key:
        log_info_blue(logger, f"    Adding SSH key to VM {vmid} on {node_name}")
        # For cloud-init in Proxmox, SSH keys need to be URL-encoded
        import urllib.parse

        params_to_set["sshkeys"] = urllib.parse.quote(ssh_key)

    try:
        # Proxmox API uses PUT for setting/updating config options.
        result = client.nodes(node_name).qemu(vmid).config.put(**params_to_set)
        log_info_green(
            logger,
            f"      Successfully set network configuration for VM {vmid}. Result: {result}",
        )
        return str(result)
    except ResourceException as e:
        logger.error(
            f"      Failed to set network config for VM {vmid}: {e.content if hasattr(e, 'content') and e.content else str(e)}"
        )
        raise ProxmoxError(f"Could not set network config for VM {vmid}.") from e
