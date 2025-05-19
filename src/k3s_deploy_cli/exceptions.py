# file: src/k3s_deploy_cli/exceptions.py
"""Custom exceptions for the K3s deployment tool."""

class K3sDeployError(Exception):
    """Base exception for k3s-deploy-cli."""
    pass

class ProxmoxError(K3sDeployError):
    """Error related to Proxmox API interactions."""
    pass

class PveshCommandError(ProxmoxError):
    """Error specifically from a pvesh command execution."""
    def __init__(self, message: str, stderr: str = "", stdout: str = ""):
        super().__init__(message)
        self.stderr = stderr
        self.stdout = stdout

    def __str__(self) -> str:
        details = super().__str__()
        if self.stdout:
            details += f"\n  STDOUT: {self.stdout}"
        if self.stderr:
            details += f"\n  STDERR: {self.stderr}"
        return details

class NodeDiscoveryError(K3sDeployError):
    """Error during node discovery."""
    pass

class ConfigurationError(K3sDeployError):
    """Error related to configuration issues."""
    pass