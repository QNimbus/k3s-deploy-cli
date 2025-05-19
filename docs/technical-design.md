# Technical Design Document: k3s-deploy-cli

**Version:** 0.2.0 (reflecting `proxmoxer` integration and sorting)
**Date:** October 26, 2023 (Placeholder)
**Author:** B. van Wetten (Originally), AI Assistant

## 1. Introduction & Goals

`k3s-deploy-cli` is a Python command-line tool designed to automate and manage the deployment and lifecycle of K3s clusters hosted on Proxmox VE. It replaces a previous bash script, aiming for better maintainability, error handling, and extensibility.

**Key Goals:**

*   Discover Proxmox VMs based on predefined tags representing K3s node roles (server, agent, storage).
*   Perform power operations (start, stop, restart) on these discovered VMs.
*   Configure static IP addresses for these VMs using Proxmox cloud-init settings.
*   (Future) Provision a K3s cluster onto the configured VMs.
*   Check the configured K3s version against the latest available release.
*   Provide a user-friendly command-line interface.

## 2. System Architecture & Core Components

The tool is structured as a Python package (`k3s_deploy_cli`) with a `src`-layout. It uses Poetry for dependency management and packaging.

**Core Modules & Responsibilities:**

*   **`src/k3s_deploy_cli/`**: Root package directory.
    *   **`__main__.py`**: Entry point for `python -m k3s_deploy_cli`. Calls `cli.main_cli()`.
    *   **`cli.py`**: Handles command-line argument parsing using `argparse`. Defines subcommands and dispatches to `K3sDeploymentManager` methods.
    *   **`config.py`**: Stores static configuration values (e.g., default K3s version, Proxmox tags, IP ranges) and loads dynamic configuration from environment variables (e.g., Proxmox API credentials).
    *   **`exceptions.py`**: Defines custom exception classes (`K3sDeployError`, `ProxmoxError`, `ConfigurationError`, `NodeDiscoveryError`) for structured error handling.
    *   **`k3s_manager.py`**: Contains the `K3sDeploymentManager` class, which orchestrates all core logic:
        *   Node discovery (from Proxmox tags or a `config.json` file).
        *   VM power management.
        *   IP configuration.
        *   K3s version checking.
        *   (Future) K3s provisioning logic.
        *   Manages state (lists of discovered server, agent, storage nodes).
    *   **`logging_utils.py`**: Provides a reusable logger with colorized console output for different log levels.
    *   **`models.py`**: Defines data classes for representing Proxmox entities:
        *   `VMIdentifier`: Represents a specific VM (proxmox_node, vmid, name, tags, IP, config).
        *   `ProxmoxNode`: (Currently less used directly, but could represent a physical Proxmox host).
    *   **`proxmox_api.py`**: Handles all direct communication with the Proxmox VE API using the `proxmoxer` library.
        *   Manages client initialization and authentication (password or API token).
        *   Provides functions to get cluster nodes, VMs on a node, VM config, VM status, control VMs, and set VM network config.

**External Dependencies:**

*   `requests`: Used by `k3s_manager.py` to check the latest K3s version from GitHub.
*   `proxmoxer`: Used by `proxmox_api.py` to interact with the Proxmox VE API.

**System Dependencies (for the environment, not Python libraries):**
*   None explicitly required by the Python code itself after the `proxmoxer` integration. `pvesh` and `jq` are no longer direct dependencies.

## 3. Data Models & State

*   **`VMIdentifier` (`models.py`):**
    *   `proxmox_node: str` (e.g., "pve1")
    *   `vmid: int` (e.g., 101)
    *   `name: Optional[str]` (VM name from Proxmox)
    *   `ip_address: Optional[str]` (Currently not actively populated/used post-discovery, but available for future use)
    *   `tags: List[str]` (List of tags associated with the VM in Proxmox)
    *   `config: Dict[str, Any]` (Raw VM configuration dictionary from Proxmox, fetched as needed)
*   **`K3sDeploymentManager` State:**
    *   `servers: List[VMIdentifier]`
    *   `agents: List[VMIdentifier]`
    *   `storage: List[VMIdentifier]`
    *   `all_nodes: List[VMIdentifier]` (Unique set of all discovered K3s role VMs)
    *   `server_master: Optional[VMIdentifier]` (The first server in the sorted `servers` list)
    *   `servers_no_first: List[VMIdentifier]` (Remaining servers)
    *   `k3s_version: str` (The K3s version to use/check)

## 4. Core Workflows & Logic

### 4.1. Node Discovery (`k3s_manager.py -> discover_nodes_by_tags`)

1.  **Fetch Proxmox Cluster Nodes:** Calls `proxmox_api.get_proxmox_cluster_nodes()` to get a list of physical Proxmox server names (e.g., "pve1", "pve2").
2.  **Iterate Physical Nodes:** For each physical Proxmox node:
    a.  **Fetch VMs on Node:** Calls `proxmox_api.get_vms_on_node(node_name)`. If a node is unreachable (e.g., "No route to host"), a warning is logged, and an empty list is returned for that node; discovery continues.
    b.  **Iterate VMs:** For each VMID found on the physical node:
        i.  **Fetch VM Config:** Calls `proxmox_api.get_vm_config(node_name, vmid)` to get tags and name. If this fails, the VM is skipped with a warning.
        ii. **Tag Matching:** Checks if VM tags (semicolon-separated in Proxmox, split into a list) contain `config.SERVER_TAG`, `config.AGENT_TAG`, or `config.STORAGE_TAG`.
        iii. **Categorization:** If a role tag matches, a `VMIdentifier` object is created (including its name and all tags) and added to the respective list (`servers`, `agents`, `storage`) and to `all_nodes`.
3.  **Deduplication & Sorting:** The collected lists (`all_nodes`, `servers`, `agents`, `storage`) are deduplicated (using `list(set(...))`) and then sorted deterministically by `(proxmox_node, vmid)` via the `_populate_node_lists` method.
4.  **Master Selection:** The first VM in the sorted `servers` list is designated as `server_master`.

### 4.2. Loading Nodes from `config.json` (`k3s_manager.py -> load_nodes_from_config_file`)

*   If `./config.json` exists, it's parsed.
*   Expected format (example):
    ```json
    {
      "nodes": [
        {
          "id": "pve1",
          "vms": [
            {"vmid": 101, "role": "SERVER", "name": "k3s-master-01", "ip": "10.10.0.50"},
            {"vmid": 102, "role": "AGENT"}
          ]
        }
      ]
    }
    ```
*   VMs are parsed into `VMIdentifier` objects and categorized.
*   This method can pre-populate node lists, potentially with direct IP addresses if included in the JSON, which is useful for provisioning if IPs are known and static outside of cloud-init.
*   The `ensure_nodes_are_discovered` method prioritizes `config.json` if it exists and contains nodes, otherwise falls back to tag-based discovery.

### 4.3. VM Power Actions (`k3s_manager.py -> perform_vm_action`)

1.  Ensures nodes are discovered (via `ensure_nodes_are_discovered`).
2.  Iterates through `self.all_nodes`.
3.  For each `VMIdentifier`:
    a.  Calls `proxmox_api.get_vm_status()` to get current VM status (e.g., "running", "stopped").
    b.  Based on the requested action (`start`, `stop`, `restart`) and current status:
        *   **Start:** If stopped, calls `proxmox_api.control_vm(..., "start")`.
        *   **Stop (Graceful):** If running, calls `proxmox_api.control_vm(..., "stop")` (which maps to Proxmox API's "shutdown").
        *   **Restart:** If running, calls `proxmox_api.control_vm(..., "reboot")`. If not running, attempts to start it.
    c.  Logs actions and results.

### 4.4. IP Configuration (`k3s_manager.py -> configure_ips`)

1.  Ensures nodes are discovered.
2.  Nodes in `self.all_nodes` are sorted by `(proxmox_node, vmid)` for deterministic IP assignment.
3.  Iterates through an IP address range defined in `config.py` (`K3S_NODE_IP_RANGE_START` to `_END`).
4.  For each `VMIdentifier` in the sorted list:
    a.  Assigns the next available IP from the range.
    b.  Fetches current VM config (`proxmox_api.get_vm_config()`) if not already available on the `VMIdentifier` object (for idempotency check).
    c.  Constructs target Proxmox cloud-init parameters:
        *   `ipconfigX` (e.g., `ip=10.10.0.201/24,gw=10.10.0.1`)
        *   `nameserver`
        *   `searchdomain`
    d.  **Idempotency Check:** Compares target parameters with current values in VM config. If identical, skips update.
    e.  If changes are needed, calls `proxmox_api.set_vm_network_config()` with the new parameters. This uses a `PUT` request via `proxmoxer`.
    f.  Logs actions and reminds the user that a reboot might be needed for cloud-init to apply settings.

### 4.5. K3s Version Check (`k3s_manager.py -> check_k3s_version`)

1.  Makes an HTTP GET request to `config.K3S_RELEASES_URL` (GitHub API) using `requests`.
2.  Parses the JSON response to get the `tag_name` of the latest release.
3.  Compares with `self.k3s_version`.
4.  If different, informs the user. If `ask_update` is true, prompts to update the version used by the script.

### 4.6. (Future) K3s Provisioning (`k3s_manager.py -> provision_k3s_cluster`)

*   This is currently a placeholder.
*   **Design Considerations for Implementation:**
    *   **Prerequisite:** VMs must have IPs assigned and be reachable. The `configure-ips` step aims to set this up via cloud-init. A subsequent step might be needed to *verify/discover* these applied IPs before provisioning if they are not statically known from `config.json`.
    *   **Remote Execution:** Needs a mechanism to SSH into VMs and run commands.
        *   Consider `paramiko` for direct SSH.
        *   Consider `fabric` for higher-level task definitions.
        *   Alternatively, generate an Ansible inventory and run an Ansible playbook.
    *   **Steps:**
        1.  Install K3s on the `server_master`.
            *   Construct `INSTALL_K3S_EXEC` string.
            *   Set `K3S_URL` if installing additional masters.
            *   Retrieve K3s token from the first master.
        2.  Install K3s on other servers (`servers_no_first`), joining the cluster.
        3.  Install K3s on agents (`agents`), joining the cluster.
        4.  Install KubeVIP on server nodes for HA control plane (if `KUBE_VIP_VERSION` is set).
        5.  Deploy MetalLB or other load balancer solutions using manifests (using `kubectl apply -f ...` remotely).
        6.  (Optional) Deploy Longhorn or other storage solutions on `storage` nodes.

## 5. Configuration (`config.py` and Environment Variables)

*   **Static Config (`config.py`):**
    *   `KUBE_VIP_VERSION`, `K3S_VERSION` (default)
    *   `SERVER_TAG`, `AGENT_TAG`, `STORAGE_TAG`
    *   `K3S_NODE_IP_RANGE_START`/`_END`/`_CIDR`/`_GATEWAY`/`_DNS_SERVERS`/`_SEARCH_DOMAIN`/`_IPCONFIG_INDEX`
    *   `VIP_ADDRESS`, `LOADBALANCER_IP_RANGE` (for MetalLB)
    *   `K3S_RELEASES_URL`
*   **Environment Variables (for Proxmox API connection):**
    *   `PROXMOX_HOST` (required)
    *   `PROXMOX_PORT` (default: 8006)
    *   `PROXMOX_USER` (required, format: `username@realm`, e.g., `root@pam`)
    *   `PROXMOX_PASSWORD` (if using password auth)
    *   `PROXMOX_API_TOKEN_ID` (if using token auth, the token name)
    *   `PROXMOX_API_TOKEN_SECRET` (if using token auth, the secret value)
    *   `PROXMOX_SSL_VERIFY` (default: "true"; set to "false" or "0" to disable SSL verification for self-signed certs)
*   **Local Node Configuration (`./config.json`):**
    *   Optional file to predefine nodes, their roles, and potentially IPs, bypassing tag discovery.

## 6. Error Handling & Logging

*   **Custom Exceptions (`exceptions.py`):** Used to signal specific error conditions.
*   **`try-except` blocks:** Implemented in `proxmox_api.py` for `ResourceException` from `proxmoxer` and other connection issues. `K3sDeploymentManager` catches these and its own custom exceptions. `cli.py` has a top-level try-except to catch `K3sDeployError` and provide user-friendly messages.
*   **Logging (`logging_utils.py`):**
    *   Colorized console output.
    *   Different log levels used for information, warnings, errors.
    *   `log_info_blue`, `log_info_green`, `log_info_yellow` helpers for specific message types.
*   **Graceful Degradation:**
    *   If a Proxmox node is unreachable during discovery, it's skipped with a warning, and discovery proceeds for other nodes.

## 7. Future Enhancements & Considerations

*   **Full K3s Provisioning Logic:** Implement the detailed steps outlined in section 4.6.
*   **Idempotency for Provisioning:** Ensure provisioning steps can be re-run without adverse effects.
*   **Cluster Teardown/Deletion:** Add a command to remove K3s and potentially delete VMs.
*   **K3s Upgrade Management:**
*   **State Management for Provisioned IPs:** If IPs are assigned by cloud-init and not known beforehand, a mechanism to query/discover these IPs post-reboot and store them (perhaps in an updated `config.json` or a state file) will be crucial for provisioning.
*   **Configuration of `KUBE_VIP_VERSION`, `VIP_ADDRESS`, `LOADBALANCER_IP_RANGE`:** Currently, these are static in `config.py`. They should be actively used during the provisioning phase.
*   **Testing:** Implement unit tests (e.g., using `pytest` and `unittest.mock`) for `k3s_manager.py` and `proxmox_api.py` (mocking `proxmoxer` calls).
*   **More Sophisticated `config.json` Handling:** Allow `config.json` to be the sole source of truth if present, potentially with richer VM details.
*   **SSH Key Management:** For provisioning, consider how SSH keys will be managed/distributed to target VMs.

## 8. Setup & Usage

1.  Clone repository.
2.  Install Poetry.
3.  Run `poetry install` to create venv and install dependencies.
4.  Set Proxmox API environment variables.
5.  Run `poetry shell` or activate venv.
6.  Execute: `python -m k3s_deploy_cli <command> [options]`
    *   Example: `python -m k3s_deploy_cli stop`
    *   Example: `python -m k3s_deploy_cli configure-ips`
