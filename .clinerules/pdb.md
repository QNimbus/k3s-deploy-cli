# Product Design Brief: K3s Deployment CLI for Proxmox VE

**Product Name:** K3s Deployment CLI (k3s-deploy-cli)
**Version:** 0.2 (Alpha/Beta)
**Date:** October 26, 2023 (Placeholder)
**Target Users:** DevOps Engineers, System Administrators, Home Lab Enthusiasts, K3s Users utilizing Proxmox VE.

## 1. Project Vision & Goals

**Vision:** To provide a simple, reliable, and efficient command-line tool that significantly streamlines the deployment and basic lifecycle management of K3s Kubernetes clusters on the Proxmox VE virtualization platform.

**Core User Problem:** Manually setting up and managing K3s clusters on multiple Proxmox VMs is time-consuming, error-prone, and lacks repeatability. Users need an automated way to discover, configure, and manage these VMs as K3s nodes.

**Product Goals:**

*   **Automate VM Discovery:** Eliminate manual tracking of VMs intended for K3s by discovering them based on Proxmox tags.
*   **Simplify VM Management:** Offer straightforward commands for common power operations (start, stop, restart) targeting K3s cluster VMs.
*   **Standardize Network Configuration:** Automate the assignment of static IP addresses to K3s VMs via Proxmox cloud-init, ensuring consistent network setups.
*   **Facilitate K3s Provisioning (Future):** Lay the groundwork for and eventually implement automated K3s installation and cluster bootstrapping.
*   **Improve Operational Efficiency:** Reduce the manual effort and time required to manage K3s on Proxmox.
*   **Enhance Reliability:** Provide a more robust and error-tolerant solution compared to ad-hoc scripting.

## 2. Target Audience & User Scenarios

**Primary Users:**

*   **DevOps Engineers/SREs:** Managing development, staging, or small production K3s clusters on Proxmox.
*   **System Administrators:** Setting up internal K3s clusters for various services on company-managed Proxmox infrastructure.
*   **Home Lab Enthusiasts:** Experimenting with Kubernetes, learning K3s, and running personal projects on Proxmox.

**Key User Scenarios:**

1.  **Initial Cluster Setup:**
    *   "As a DevOps engineer, I want to quickly tag new VMs in Proxmox and then use the CLI to assign them static IPs from a predefined range so they are ready for K3s installation."
    *   (Future) "As a sysadmin, after configuring IPs, I want to run a single command to install K3s on all designated server and agent nodes and form a basic cluster."
2.  **Cluster Maintenance:**
    *   "As a home lab user, I want to easily start all my K3s cluster VMs with one command when I begin working on a project."
    *   "As an SRE, I need to gracefully shut down all K3s VMs for scheduled Proxmox host maintenance."
3.  **Version Awareness:**
    *   "As a K3s user, I want to quickly check if the K3s version I plan to use (or have deployed) is the latest available, so I can consider upgrading."
4.  **Troubleshooting/Discovery:**
    *   "As an administrator, I want to easily list all VMs currently designated as part of my K3s cluster based on their Proxmox tags."

## 3. Core Features & Functionality

The CLI will provide the following commands:

*   **`discover` (Implicit):**
    *   Automatically discover Proxmox VMs tagged for K3s roles (server, agent, storage).
    *   Option to load node definitions from a local `config.json` file.
*   **`start`:**
    *   Starts all discovered K3s VMs.
    *   Idempotent: does not error if VMs are already running.
*   **`stop`:**
    *   Gracefully shuts down all discovered K3s VMs.
    *   Idempotent: does not error if VMs are already stopped.
*   **`restart`:**
    *   Restarts all discovered K3s VMs. (Starts them if not running).
*   **`configure-ips`:**
    *   Assigns static IP addresses, gateways, and DNS settings to discovered K3s VMs from a predefined range using Proxmox cloud-init parameters.
    *   Idempotent: checks existing configuration and only applies changes if necessary.
*   **`check-version`:**
    *   Compares the K3s version configured in the tool against the latest stable release from GitHub.
    *   Optionally allows updating the tool's configured K3s version.
*   **`provision` (Future):**
    *   Installs K3s on configured server and agent nodes.
    *   Sets up the K3s cluster (master initialization, node joining).
    *   (Optional) Deploys KubeVIP for control plane high availability.
    *   (Optional) Deploys MetalLB for LoadBalancer services.
*   **`help`:**
    *   Displays usage information and command details.

## 4. Design & User Experience Principles

*   **CLI First:** All interactions are through the command line.
*   **Simplicity:** Commands should be intuitive and easy to remember.
*   **Idempotency:** Operations, where applicable (e.g., `start`, `stop`, `configure-ips`), should be safe to run multiple times without unintended side effects.
*   **Clear Feedback:** Provide informative output about actions being performed, successes, warnings, and errors. Use colorized logging for readability.
*   **Configuration over Convention (with Defaults):**
    *   Key operational parameters (Proxmox tags, IP ranges) are configurable.
    *   Proxmox API credentials managed via environment variables for security.
    *   Sensible defaults provided.
*   **Graceful Error Handling:** The tool should handle common issues (e.g., an unreachable Proxmox node in a cluster) gracefully, providing warnings and continuing where possible.

## 5. Success Metrics

*   **Adoption:** Number of users/downloads (if publicly distributed).
*   **Time Savings:** Reduction in time spent manually performing K3s deployment and management tasks on Proxmox.
*   **Reduced Errors:** Fewer configuration mistakes compared to manual processes.
*   **User Feedback:** Positive feedback regarding ease of use and reliability.
*   **Feature Completion:** Successful implementation of the `provision` command.

## 6. Future Considerations (Beyond Core Scope)

*   Interactive mode for guided setup.
*   K3s cluster upgrade workflows.
*   Cluster teardown and VM deletion.
*   Integration with secrets management for Proxmox credentials.
*   More advanced node role definitions or custom tag support.
*   Generating Ansible inventories or Terraform configurations.