## Running the Project

The project uses Poetry for dependency management. To run the application:

1. **Setup**:
   ```bash
   # Clone the repository
   git clone <repository-url>
   cd k3s-deploy
   
   # Install dependencies using Poetry
   poetry install
   ```

2. **Running Commands**:
   ```bash
   # Using Poetry run
   poetry run python -m k3s_deploy_cli <command> [options]
   
   # Or activate the virtual environment first
   poetry shell
   python -m k3s_deploy_cli <command> [options]
   ```

3. **Example Commands**:
   ```bash
   # Check K3s version
   poetry run python -m k3s_deploy_cli check-version
   
   # Configure VMs with static IPs and SSH keys
   poetry run python -m k3s_deploy_cli configure-vm
   
   # Configure VMs and force update even if no changes detected
   poetry run python -m k3s_deploy_cli configure-vm --force
   
   # Configure VMs and restart them automatically
   poetry run python -m k3s_deploy_cli configure-vm --restart
   ```
