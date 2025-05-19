#!/usr/bin/env python3
"""Test script to verify dotenv functionality."""

import os

from k3s_deploy_cli import config

print("Environment variables:")
print(f"PROXMOX_HOST: {os.environ.get('PROXMOX_HOST')}")
print(f"PROXMOX_USER: {os.environ.get('PROXMOX_USER')}")
print(f"PROXMOX_PASSWORD: {os.environ.get('PROXMOX_PASSWORD')}")

print("\nConfig values:")
print(f"PROXMOX_HOST: {config.PROXMOX_HOST}")
print(f"PROXMOX_USER: {config.PROXMOX_USER}")
print(f"PROXMOX_PASSWORD: {config.PROXMOX_PASSWORD}")
