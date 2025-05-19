# file: src/k3s_deploy_cli/cli.py
"""
Command-Line Interface for the K3s Deployment Tool.
Uses argparse to handle commands and options.
"""
import argparse
import sys
import subprocess # <--- Added missing import here

from .k3s_manager import K3sDeploymentManager
from .logging_utils import logger, log_info_green, log_info_blue
from . import config as app_config # To show current K3S_VERSION in help
from .exceptions import K3sDeployError

def create_parser() -> argparse.ArgumentParser:
    """Creates and returns the argparse.ArgumentParser instance."""
    parser = argparse.ArgumentParser(
        description="Python tool to manage K3s deployments on Proxmox.",
        formatter_class=argparse.RawTextHelpFormatter # For better help text formatting
    )
    # Keep a reference to the original K3S_VERSION for the help message
    original_k3s_version = app_config.K3S_VERSION

    # Subparsers for commands
    subparsers = parser.add_subparsers(dest="command", title="Commands",
                                       help="Action to perform. Use <command> -h for specific help.")
    subparsers.required = True # A command must be provided

    # Start command
    parser_start = subparsers.add_parser("start", help="Start Proxmox VMs with k3s role tags.")
    parser_start.set_defaults(func=handle_vm_action, action_name="start")

    # Stop command
    parser_stop = subparsers.add_parser("stop", help="Gracefully shutdown Proxmox VMs with k3s role tags.")
    parser_stop.set_defaults(func=handle_vm_action, action_name="stop")

    # Restart command
    parser_restart = subparsers.add_parser("restart", help="Restart Proxmox VMs with k3s role tags.")
    parser_restart.set_defaults(func=handle_vm_action, action_name="restart")

    # Configure-IPs command
    parser_configure_ips = subparsers.add_parser(
        "configure-ips",
        help="Assign static IPs from the defined range to VMs with k3s role tags."
    )
    parser_configure_ips.set_defaults(func=handle_configure_ips)

    # Provision command
    parser_provision = subparsers.add_parser(
        "provision",
        help="Setup and provision the K3s cluster on all nodes.\n"
             "(IMPORTANT: Assumes nodes are accessible, ideally via IPs configured by 'configure-ips')"
    )
    parser_provision.set_defaults(func=handle_provision)

    # Check-version command
    parser_check_version = subparsers.add_parser(
        "check-version",
        help=f"Check if the current K3s version ({original_k3s_version}) is the latest available."
    )
    parser_check_version.add_argument(
        "--update", action="store_true",
        help="Ask to update the K3S_VERSION used by the script if a newer one is found."
    )
    parser_check_version.set_defaults(func=handle_check_version)

    # Help message augmentation (similar to the bash script's usage footer)
    epilog_parts = [
        "\nVM Node Types (Proxmox Tags):",
        f"  Server nodes should have the '{app_config.SERVER_TAG}' tag.",
        f"  Agent nodes should have the '{app_config.AGENT_TAG}' tag.",
        f"  Storage nodes should have the '{app_config.STORAGE_TAG}' tag (if used for specific storage roles).",
        "\nConfiguration:",
        f"  Key settings are in src/k3s_deploy_cli/config.py",
        f"  Node information can be pre-loaded from: {app_config.NODE_CONFIG_FILE.resolve()}",
    ]
    parser.epilog = "\n".join(epilog_parts)

    return parser

def handle_vm_action(args: argparse.Namespace, manager: K3sDeploymentManager) -> None:
    """Handles start, stop, restart VM actions."""
    manager.perform_vm_action(args.action_name)

def handle_configure_ips(args: argparse.Namespace, manager: K3sDeploymentManager) -> None:
    """Handles the configure-ips action."""
    manager.configure_ips()

def handle_provision(args: argparse.Namespace, manager: K3sDeploymentManager) -> None:
    """Handles the provision action."""
    manager.provision_k3s_cluster()

def handle_check_version(args: argparse.Namespace, manager: K3sDeploymentManager) -> None:
    """Handles the check-version action."""
    manager.check_k3s_version(ask_update=args.update)


def main_cli():
    """Main entry point for the CLI application."""
    parser = create_parser()
    args = parser.parse_args()

    manager = K3sDeploymentManager()

    try:
        log_info_blue(logger, f"Executing command: {args.command}")
        args.func(args, manager) # Call the appropriate handler function
        log_info_green(logger, f"Command '{args.command}' completed successfully.")

    except K3sDeployError as e:
        logger.error(f"An application error occurred: {e}")
        # Check if it's a PveshCommandError and has stderr to print
        pvesh_error_details = getattr(e, 'stderr', None)
        if pvesh_error_details:
             logger.error(f"  Underlying pvesh error output: {pvesh_error_details}")
        sys.exit(1)
    except SystemExit: # Allow sys.exit() to propagate
        raise
    except Exception as e: # Catch-all for unexpected errors
        logger.critical(f"An unexpected critical error occurred: {e}", exc_info=True)
        sys.exit(2)