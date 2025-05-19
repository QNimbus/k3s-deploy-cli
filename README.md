# K3s Deployment CLI for Proxmox VE

A Python command-line tool designed to automate and manage the deployment and lifecycle of K3s clusters hosted on Proxmox VE. This tool simplifies the process of discovering, configuring, and managing VMs as K3s nodes.

## Overview

K3s-deploy-cli replaces manual, error-prone processes with a streamlined CLI that:

- Automatically discovers Proxmox VMs based on tags
- Manages VM power operations (start, stop, restart)
- Configures static IP addresses and SSH keys via cloud-init
- Checks K3s version against the latest available release
- (Future) Provisions K3s clusters onto configured VMs

## Prerequisites

- Python 3.12 or higher
- Poetry (for dependency management)
- Proxmox VE environment with API access
- VMs tagged appropriately in Proxmox (default tags: `k3s-server`, `k3s-agent`, `k3s-storage`)
- Cloud-init enabled on target VMs

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd k3s-deploy

# Install dependencies using Poetry
poetry install
```

## Configuration

### Environment Variables

The application uses environment variables for configuration. You can set these in your shell or use a `.env` file in the project root directory.

**Required Variables:**
- `PROXMOX_HOST`: Hostname or IP address of your Proxmox server
- `PROXMOX_USER`: Proxmox username with API access (format: `username@realm`, e.g., `root@pam`)

**Authentication (one of the following is required):**
- `PROXMOX_PASSWORD`: Password for Proxmox user
- `PROXMOX_API_TOKEN_ID` and `PROXMOX_API_TOKEN_SECRET`: API token credentials

**Optional Variables:**
- `PROXMOX_PORT`: Proxmox API port (default: 8006)
- `PROXMOX_SSL_VERIFY`: Set to "false" or "0" to disable SSL verification for self-signed certificates
- `K3S_SSH_PUBLIC_KEY`: SSH public key content for VM configuration
- `K3S_SSH_PUBLIC_KEY_PATH`: Path to SSH public key file (default: `~/.ssh/id_rsa.pub`)

Example `.env` file:
```
PROXMOX_HOST=pve.example.com
PROXMOX_USER=root@pam
PROXMOX_PASSWORD=your-password
```

### VM Tagging in Proxmox

Tag your VMs in Proxmox with the following tags to designate their roles:
- `k3s-server`: For K3s server nodes (control plane)
- `k3s-agent`: For K3s agent nodes (workers)
- `k3s-storage`: For storage nodes

## Usage

### Running Commands

```bash
# Using Poetry run
poetry run python -m k3s_deploy_cli <command> [options]

# Or activate the virtual environment first
poetry shell
python -m k3s_deploy_cli <command> [options]
```

### Available Commands

#### VM Power Management

```bash
# Start all K3s VMs
poetry run python -m k3s_deploy_cli start

# Stop all K3s VMs
poetry run python -m k3s_deploy_cli stop

# Restart all K3s VMs
poetry run python -m k3s_deploy_cli restart
```

#### VM Configuration

```bash
# Configure VMs with static IPs and SSH keys
poetry run python -m k3s_deploy_cli configure-vm

# Configure VMs and force update even if no changes detected
poetry run python -m k3s_deploy_cli configure-vm --force

# Configure VMs and restart them automatically
poetry run python -m k3s_deploy_cli configure-vm --restart
```

#### K3s Version Management

```bash
# Check K3s version against latest release
poetry run python -m k3s_deploy_cli check-version

# Check K3s version and prompt to update if newer version available
poetry run python -m k3s_deploy_cli check-version --update
```

#### Future Commands

```bash
# Provision K3s cluster (not yet implemented)
poetry run python -m k3s_deploy_cli provision
```

## Advanced Configuration

### Using config.json

You can define your nodes explicitly in a `config.json` file in the project root directory. This bypasses tag-based discovery and allows you to specify additional details like IP addresses.

Example `config.json`:
```json
{
  "nodes": [
    {
      "id": "pve1",
      "vms": [
        {"vmid": 101, "role": "SERVER", "name": "k3s-master-01", "ip": "10.10.0.50"},
        {"vmid": 102, "role": "AGENT", "name": "k3s-worker-01"}
      ]
    }
  ]
}
```

## Troubleshooting

### Common Issues

1. **Connection Errors**:
   - Verify Proxmox API credentials in your `.env` file
   - Check if Proxmox API is accessible from your machine
   - If using self-signed certificates, set `PROXMOX_SSL_VERIFY=false`

2. **VM Discovery Issues**:
   - Ensure VMs are properly tagged in Proxmox
   - Check if the Proxmox user has sufficient permissions

3. **Cloud-init Configuration**:
   - Ensure VMs have cloud-init enabled
   - Remember that cloud-init changes require a VM restart to take effect

### Logs

The application uses colorized logging to provide clear feedback about operations. Pay attention to warnings and errors in the output.

## License

MIT License
