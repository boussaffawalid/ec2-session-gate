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
from typing import Optional, Tuple

def which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)

def require_cmd(cmd: str, friendly: str):
    if not which(cmd):
        raise RuntimeError(f"Required tool '{cmd}' not found. Please install {friendly}.")

_HOST_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
# EC2 instance ID format: i-[0-9a-f]{8,17} (8-17 hex digits after 'i-')
_INSTANCE_ID_RE = re.compile(r"^i-[0-9a-f]{8,17}$", re.IGNORECASE)
# Connection ID format: UUID (8-4-4-4-12 hex digits)
_CONNECTION_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)

def validate_remote_host(host: str) -> bool:
    """Validate remote hostname/IP address format."""
    if not host:
        return False
    return bool(_HOST_RE.match(host))

def validate_port(port: int) -> bool:
    """Validate port number is in valid range (1-65535)."""
    from .constants import MIN_PORT, MAX_PORT
    return isinstance(port, int) and MIN_PORT <= port <= MAX_PORT

def validate_port_range(start: int, end: int) -> Tuple[bool, Optional[str]]:
    """
    Validate port range.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    from .constants import MIN_PORT, MAX_PORT, SYSTEM_PORT_MAX
    
    if not isinstance(start, int) or not isinstance(end, int):
        return False, "Port range values must be integers"
    
    if start < MIN_PORT or start > MAX_PORT:
        return False, f"Start port {start} is out of valid range ({MIN_PORT}-{MAX_PORT})"
    
    if end < MIN_PORT or end > MAX_PORT:
        return False, f"End port {end} is out of valid range ({MIN_PORT}-{MAX_PORT})"
    
    if start >= end:
        return False, f"Start port {start} must be less than end port {end}"
    
    # Warn about system ports (0-1023) but allow them
    if start < SYSTEM_PORT_MAX:
        logger.warning(f"Port range starts below {SYSTEM_PORT_MAX} (system ports): {start}-{end}")
    
    return True, None

def validate_instance_id(instance_id: str) -> Tuple[bool, Optional[str]]:
    """
    Validate EC2 instance ID format.
    
    Args:
        instance_id: Instance ID to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not instance_id:
        return False, "Instance ID cannot be empty"
    
    if not isinstance(instance_id, str):
        return False, "Instance ID must be a string"
    
    if not _INSTANCE_ID_RE.match(instance_id):
        return False, f"Invalid instance ID format: {instance_id}. Expected format: i-xxxxxxxx (8-17 hex digits)"
    
    return True, None

def validate_connection_id(connection_id: str) -> Tuple[bool, Optional[str]]:
    """
    Validate connection ID format (UUID).
    
    Args:
        connection_id: Connection ID to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not connection_id:
        return False, "Connection ID cannot be empty"
    
    if not isinstance(connection_id, str):
        return False, "Connection ID must be a string"
    
    if not _CONNECTION_ID_RE.match(connection_id):
        return False, f"Invalid connection ID format: {connection_id}. Expected UUID format"
    
    return True, None

def sanitize_string(value: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize string input to prevent injection attacks.
    
    Args:
        value: String to sanitize
        max_length: Optional maximum length
        
    Returns:
        Sanitized string
    """
    if not isinstance(value, str):
        return ""
    
    # Remove null bytes and control characters except newline and tab
    sanitized = "".join(c for c in value if ord(c) >= 32 or c in "\n\t")
    
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized
