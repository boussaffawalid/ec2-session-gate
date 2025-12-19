import os
import subprocess
import psutil
import logging
import time

logger = logging.getLogger(__name__)

def kill_process_tree(pid):
    """Kill a process and all its children"""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        
        for child in children:
            try:
                child.terminate()
                child.wait(timeout=5)
            except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                child.kill() if child.is_running() else None
        
        parent.terminate()
        try:
            parent.wait(timeout=5)
        except psutil.TimeoutExpired:
            parent.kill()
            
        return True
    except psutil.NoSuchProcess:
        logger.warning(f"Process {pid} no longer exists")
        return False
    except Exception as e:
        logger.error(f"Error killing process tree: {str(e)}")
        return False

def check_aws_dependencies():
    """Check if required AWS CLI and plugins are installed"""
    try:
        # Windows-specific creation flags
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        
        # Check AWS CLI
        subprocess.check_output(
            ["aws", "--version"], 
            stderr=subprocess.STDOUT,
            **kwargs
        )
        
        # Check SSM plugin
        subprocess.check_output(
            ["aws", "ssm", "start-session", "--version"],
            stderr=subprocess.STDOUT,
            **kwargs
        )
        
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.error(f"AWS dependencies check failed: {str(e)}")
        return False

def monitor_connections(connections):
    """Monitor active connections and remove dead ones"""
    dead_connections = []
    for conn in connections:
        if conn['process'].poll() is not None:
            dead_connections.append(conn)
    
    for conn in dead_connections:
        connections.remove(conn)
    
    return len(dead_connections)

def create_success_response(payload=None):
    return {'status':'success', **(payload or {})}

def create_error_response(msg):
    return {'status':'error','error':msg}

import shutil, platform, subprocess, re
from typing import Optional

def which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)

def require_cmd(cmd: str, friendly: str):
    if not which(cmd):
        raise RuntimeError(f"Required tool '{cmd}' not found. Please install {friendly}.")

_HOST_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
def validate_remote_host(host: str) -> bool:
    return bool(_HOST_RE.match(host or ""))

def validate_port(port: int) -> bool:
    return isinstance(port, int) and 1 <= port <= 65535
