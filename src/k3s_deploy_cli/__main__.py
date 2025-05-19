# file: src/k3s_deploy_cli/__main__.py
"""
Allows the package to be run as a script using `python -m k3s_deploy_cli`.
"""
from .cli import main_cli

def main():
    """Entry point for the script when called as a module."""
    main_cli()

if __name__ == "__main__":
    main()