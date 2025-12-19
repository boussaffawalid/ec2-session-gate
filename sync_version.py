#!/usr/bin/env python3
"""
Helper script to sync version from src/version.py to pyproject.toml.

This ensures pyproject.toml stays in sync with the single source of truth.
"""
import re
from pathlib import Path

def sync_version():
    """Read version from src/version.py and update pyproject.toml"""
    # Read version from src/version.py
    version_file = Path(__file__).parent / "src" / "version.py"
    if not version_file.exists():
        print(f"Error: {version_file} not found")
        return False
    
    version = None
    with open(version_file, "r") as f:
        for line in f:
            if line.startswith("__version__"):
                version = line.split("=")[1].strip().strip('"').strip("'")
                break
    
    if not version:
        print("Error: Could not find __version__ in src/version.py")
        return False
    
    print(f"Found version: {version}")
    
    # Update pyproject.toml
    pyproject_file = Path(__file__).parent / "pyproject.toml"
    if not pyproject_file.exists():
        print(f"Error: {pyproject_file} not found")
        return False
    
    content = pyproject_file.read_text()
    # Replace version line, keeping the comment if present
    pattern = r'version\s*=\s*"[^"]+"'
    new_line = f'version = "{version}"'
    updated_content = re.sub(pattern, new_line, content)
    
    if updated_content != content:
        pyproject_file.write_text(updated_content)
        print(f"Updated {pyproject_file} with version {version}")
        return True
    else:
        print(f"Version in {pyproject_file} is already {version}")
        return True

if __name__ == "__main__":
    success = sync_version()
    exit(0 if success else 1)
