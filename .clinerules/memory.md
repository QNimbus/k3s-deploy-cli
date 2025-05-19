# k3s-deploy-cli Project Memory

## Project Overview
k3s-deploy-cli is a Python command-line tool designed to automate and manage the deployment and lifecycle of K3s clusters hosted on Proxmox VE. It replaces a previous bash script implementation, aiming for better maintainability, error handling, and extensibility.

## Current State (as of May 19, 2025)
- Well-structured Python application with clear separation of concerns
- Proxmox API integration via `proxmoxer` library
- Successfully implemented features:
  - VM discovery based on Proxmox tags
  - VM power management (start/stop/restart)
  - Static IP configuration via cloud-init
  - SSH key deployment via cloud-init
  - K3s version checking against GitHub
- Placeholder implementation for K3s provisioning (primary missing functionality)

## Architecture
- Core orchestration through `K3sDeploymentManager` class
- Clean separation between CLI interface, business logic, and Proxmox API interactions
- Custom exception hierarchy for structured error handling
- Dataclasses for representing VMs and Proxmox nodes

## Immediate Focus Areas
1. **K3s Provisioning Implementation:**
   - SSH connectivity to VMs
   - K3s master server installation
   - Token retrieval 
   - Secondary server and agent joining
   - Optional components (KubeVIP, MetalLB)

2. **Design Decisions Needed:**
   - SSH connectivity approach (Paramiko vs. Fabric vs. other options)
   - Authentication method priority (key-based or password-based)
   - IP verification strategy before provisioning
   - K3s installation configuration preferences

## Next Steps
1. Finalize design decisions for provisioning implementation
2. Implement SSH connectivity module
3. Develop K3s installation workflow
4. Add support for additional components (KubeVIP, MetalLB)
5. Implement comprehensive testing

## Recent Decisions (May 19, 2025)
1. **Command Enhancement Priority:**
   - Improving the VM configuration command is prioritized before implementing full K3s provisioning
   - Command has been renamed from `configure-ips` to `configure-vm` to better reflect its expanded scope

2. **VM Configuration Design:**
   - Expanded cloud-init configuration to include both network settings and SSH key deployment
   - Using a multi-source approach for SSH public key retrieval (env var, config file, or default path)
   - Added clear user notification about VM restart requirements for applying cloud-init changes
   - Added an optional `--restart` flag to streamline the workflow

3. **Implementation Strategy:**
   - Extended the existing architecture while maintaining clear separation of concerns
   - Kept backward compatibility for IP-only configuration scenarios via legacy `configure-ips` command
   - Ensured helpful error messages for SSH key resolution failures

## Completed Tasks (May 19, 2025)
1. **Enhanced VM Configuration Command**:
   - Added VMIdentifier.status field to track VM power state
   - Implemented configure_vms method in K3sDeploymentManager to handle both IP and SSH key configuration
   - Added context-aware messaging for VM restarts (only showing messages for VMs that need it)
   - Updated CLI with new command and maintained backward compatibility

2. **CLI Improvements (May 19, 2025)**:
   - Added a '--force' command line option to update cloud-init even if no changes are detected
   - Removed '--configure-ips' command option as backward compatibility is no longer needed
   - Updated documentation with instructions on how to run the project using Poetry

3. **Next Tasks**:
   - Loading environment variables from `.env`
   - Writing a basic README.md file explaining the use-case for this Python script and how to use it. Make sure to mention all prequisites including setting the correct environment variables.

4. **Possible future Tasks**:
   - Address flake8 warnings and linting issues (line length, unused imports)
   - Add support for additional cloud-init configuration options