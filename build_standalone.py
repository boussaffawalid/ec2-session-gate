#!/usr/bin/env python3
"""
Build script for creating standalone executables using PyInstaller.
Run this script to create platform-specific standalone apps.
"""
import os
import sys
import platform
import subprocess
from pathlib import Path

def build_standalone():
    """Build standalone executable using PyInstaller."""
    system = platform.system()
    
    # Ensure PyInstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # Ensure Pillow is installed (needed for icon processing, especially on macOS)
    try:
        import PIL
        print("Pillow is available for icon processing")
    except ImportError:
        print("Pillow not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
        # Verify installation
        try:
            import PIL
            print("Pillow installed successfully")
        except ImportError:
            print("Warning: Failed to install Pillow. Icon processing may fail.")
    
    # Base directory
    base_dir = Path(__file__).parent
    src_dir = base_dir / "src"
    
    # PyInstaller command
    cmd = [
        "pyinstaller",
        "--name=ec2-session-gate",
        "--onefile",
        "--windowed",  # No console window on Windows/macOS
        "--add-data", f"{src_dir / 'static'}{os.pathsep}src/static",
        "--add-data", f"{src_dir / 'defaults.json'}{os.pathsep}src",
        "--add-data", f"{src_dir / 'logging.yaml'}{os.pathsep}src",
        "--hidden-import=webview",
        "--hidden-import=flask",
        "--hidden-import=boto3",
        "--hidden-import=botocore",
        "--hidden-import=yaml",
        "--hidden-import=cryptography",
        "--hidden-import=psutil",
        "--collect-all=webview",
        "--collect-all=flask",
        "run.py"
    ]
    
    # Platform-specific adjustments
    icon_dir = src_dir / "static" / "images"
    
    if system == "Windows":
        # Windows can use .ico files
        ico_path = icon_dir / "logo.ico"
        if ico_path.exists():
            cmd.extend([
                f"--icon={ico_path}",
            ])
        else:
            print("Warning: logo.ico not found, building without icon")
    elif system == "Darwin":  # macOS
        # macOS requires .icns format
        icns_path = icon_dir / "logo.icns"
        if icns_path.exists():
            cmd.extend([
                f"--icon={icns_path}",
            ])
        else:
            print("Warning: logo.icns not found, building without icon")
        
        cmd.extend([
            "--osx-bundle-identifier=com.ec2sessiongate.app",
        ])
    
    print(f"Building standalone executable for {system}...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        subprocess.check_call(cmd)
        print("\n✅ Build completed successfully!")
        print(f"Executable location: {base_dir / 'dist' / 'ec2-session-gate'}")
        if system == "Windows":
            print("   (Look for ec2-session-gate.exe)")
        elif system == "Darwin":
            print("   (Look for ec2-session-gate.app bundle)")
        else:
            print("   (Look for ec2-session-gate binary)")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Build failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_standalone()

