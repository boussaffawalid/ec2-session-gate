import os
import sys
import uuid
import socket
import shutil
import platform
import subprocess
import logging
import base64
import tempfile
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _is_port_free(port: int) -> bool:
    """Check if a specific port is free."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", port))
            return True
    except OSError:
        return False


def _in_range_free_port(start: int, end: int) -> int:
    """Find a free TCP port between start and end."""
    for port in range(start, end + 1):
        if _is_port_free(port):
            return port
    raise RuntimeError("No free port available in configured range")


def _require(cmd: str, friendly: str):
    """Ensure a command exists in PATH."""
    if not shutil.which(cmd):
        raise RuntimeError(f"Required tool '{cmd}' not found. Please install {friendly}.")


# Removed _open_terminal_with_command - users now run commands manually

# -------------------------------------------------------------------
# Data classes
# -------------------------------------------------------------------

@dataclass
class Connection:
    connection_id: str
    proc: Optional[subprocess.Popen]
    command: str  # Command string for manual execution
    meta: Dict[str, Any]

# -------------------------------------------------------------------
# AWS Manager
# -------------------------------------------------------------------

class AWSManager:
    def __init__(self, preferences):
        self.preferences = preferences
        self._profile: Optional[str] = None
        self._region: Optional[str] = None
        self._account_id: Optional[str] = None
        self._connections: Dict[str, Connection] = {}
        # Cleanup any orphaned processes on startup
        self._cleanup_orphaned_processes()
    
    def _cleanup_orphaned_processes(self):
        """Find and kill any orphaned AWS SSM port forwarding processes."""
        try:
            import psutil
            current_pid = os.getpid()
            orphaned_count = 0
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info.get('cmdline', [])
                    if not cmdline:
                        continue
                    
                    # Look for AWS SSM start-session processes
                    cmdline_str = ' '.join(cmdline).lower()
                    if 'aws' in cmdline_str and 'ssm' in cmdline_str and 'start-session' in cmdline_str:
                        # Check if this process is not our child (orphaned)
                        try:
                            parent = proc.parent()
                            if parent and parent.pid == current_pid:
                                continue  # This is our child, don't kill it
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                        
                        # This looks like an orphaned SSM process
                        logger.info(f"Found orphaned SSM process (PID: {proc.info['pid']}): {cmdline_str[:100]}")
                        try:
                            from .utils import kill_process_tree
                            if kill_process_tree(proc.info['pid']):
                                orphaned_count += 1
                                logger.info(f"Killed orphaned SSM process (PID: {proc.info['pid']})")
                        except Exception as e:
                            logger.warning(f"Failed to kill orphaned process {proc.info['pid']}: {e}")
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            if orphaned_count > 0:
                logger.info(f"Cleaned up {orphaned_count} orphaned SSM processes on startup")
        except ImportError:
            # psutil not available, skip orphan cleanup
            logger.debug("psutil not available, skipping orphan process cleanup")
        except Exception as e:
            logger.warning(f"Error during orphan process cleanup: {e}", exc_info=True)

    # ------------- AWS Sessions & Helpers -------------

    def session(self, profile: Optional[str] = None):
        profile = profile or self._profile
        return boto3.session.Session(profile_name=profile, region_name=self._region)

    # ------------- Basic Info -------------

    def list_profiles(self) -> List[str]:
        import configparser
        profiles = set()
        aws_dir = os.path.expanduser("~/.aws")
        for fname in ("credentials", "config"):
            path = os.path.join(aws_dir, fname)
            if not os.path.exists(path):
                continue
            cfg = configparser.ConfigParser()
            cfg.read(path)
            for sec in cfg.sections():
                if fname == "config" and sec.startswith("profile "):
                    sec = sec.replace("profile ", "", 1)
                profiles.add(sec)
        return sorted(profiles or ["default"])

    def list_regions(self) -> List[str]:
        return sorted(self.session().get_available_regions("ec2"))

    def connect(self, profile: str, region: str) -> str:
        self._profile, self._region = profile, region
        sts = self.session().client("sts", config=Config(retries={"max_attempts": 3}))
        self._account_id = sts.get_caller_identity()["Account"]
        return self._account_id

    # ------------- EC2 + SSM -------------

    def list_instances(self) -> List[Dict[str, Any]]:
        sess = self.session()
        ec2 = sess.client("ec2")
        ssm = sess.client("ssm")

        instances = []
        paginator = ec2.get_paginator("describe_instances")
        for page in paginator.paginate():
            for r in page.get("Reservations", []):
                for i in r.get("Instances", []):
                    iid = i["InstanceId"]
                    name = next((t["Value"] for t in i.get("Tags", []) if t["Key"] == "Name"), iid)
                    platform = i.get("PlatformDetails", "Linux")
                    state = i.get("State", {}).get("Name", "")
                    instances.append({
                        "id": iid,
                        "name": name,
                        "type": i.get("InstanceType", ""),
                        "state": state,
                        "os": "Windows" if "Windows" in platform else "Linux",
                        "has_ssm": False,
                    })

        managed = set()
        for page in ssm.get_paginator("describe_instance_information").paginate():
            for info in page.get("InstanceInformationList", []):
                managed.add(info["InstanceId"])
        for inst in instances:
            inst["has_ssm"] = inst["id"] in managed
        return instances

    def instance_details(self, instance_id: str) -> Dict[str, Any]:
        ec2 = self.session().client("ec2")
        resp = ec2.describe_instances(InstanceIds=[instance_id])
        i = resp["Reservations"][0]["Instances"][0]
        
        # Extract IAM Role
        iam_role = ""
        iam_profile = i.get("IamInstanceProfile")
        if iam_profile:
            arn = iam_profile.get("Arn", "")
            if arn:
                # Extract role name from ARN: arn:aws:iam::123456789012:instance-profile/role-name
                # or arn:aws:iam::123456789012:role/role-name
                parts = arn.split("/")
                if len(parts) > 1:
                    iam_role = parts[-1]
                else:
                    iam_role = arn
        
        # Extract Security Groups
        security_groups = []
        for sg in i.get("SecurityGroups", []):
            sg_id = sg.get("GroupId", "")
            sg_name = sg.get("GroupName", "")
            if sg_name:
                security_groups.append(f"{sg_name} ({sg_id})")
            else:
                security_groups.append(sg_id)
        security_groups_str = ", ".join(security_groups) if security_groups else ""
        
        return {
            "id": instance_id,
            "name": next((t["Value"] for t in i.get("Tags", []) if t["Key"] == "Name"), instance_id),
            "type": i.get("InstanceType", ""),
            "state": i.get("State", {}).get("Name", ""),
            "platform": i.get("PlatformDetails", ""),
            "private_ip": i.get("PrivateIpAddress", "") or "N/A",
            "public_ip": i.get("PublicIpAddress", "") or "N/A",
            "vpc_id": i.get("VpcId", "") or "N/A",
            "subnet_id": i.get("SubnetId", "") or "N/A",
            "iam_role": iam_role or "N/A",
            "ami_id": i.get("ImageId", "") or "N/A",
            "key_name": i.get("KeyName", "") or "N/A",
            "security_groups": security_groups_str or "N/A",
        }

    # ------------- Port Forwarding & Sessions -------------

    def _spawn_background_process(self, cmd: list[str]) -> subprocess.Popen:
        """Spawn a background process for port forwarding."""
        # Windows-specific creation flags
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        return subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            start_new_session=True,   # critical: detach from terminal
            **kwargs
        )
    
    def _get_ssh_key_folders(self) -> List[str]:
        """
        Get list of SSH key folders from preferences.
        Supports multiple directories separated by newlines or commas.
        
        Returns:
            List of folder paths (expanded)
        """
        ssh_key_folder = getattr(self.preferences, "ssh_key_folder", None)
        folders = []
        
        if ssh_key_folder:
            # Split by newline first, then by comma (supports both formats)
            folder_strings = []
            for line in ssh_key_folder.split('\n'):
                folder_strings.extend([f.strip() for f in line.split(',') if f.strip()])
            
            # Remove duplicates while preserving order
            seen = set()
            unique_folders = []
            for folder_str in folder_strings:
                if folder_str and folder_str not in seen:
                    seen.add(folder_str)
                    unique_folders.append(folder_str)
            
            for folder_str in unique_folders:
                expanded = os.path.expanduser(folder_str)
                if os.path.exists(expanded) and os.path.isdir(expanded):
                    folders.append(expanded)
        else:
            # Default to ~/.ssh if no preference is set
            default_ssh_dir = os.path.expanduser("~/.ssh")
            if os.path.exists(default_ssh_dir) and os.path.isdir(default_ssh_dir):
                folders.append(default_ssh_dir)
        
        return folders

    def _construct_ssh_key_path(self, key_name: str) -> Optional[str]:
        """
        Construct SSH key path based on preferences and key name.
        Searches through multiple directories if configured.
        
        Args:
            key_name: Name of the SSH key
            
        Returns:
            Constructed key path or None if key_name is invalid
        """
        if not key_name or key_name == "N/A":
            return None
        
        # Get list of SSH key folders to search
        ssh_key_folders = self._get_ssh_key_folders()
        
        # Search through all configured folders
        for ssh_key_folder in ssh_key_folders:
            # Try with and without .pem extension
            key_path_without_ext = os.path.join(ssh_key_folder, key_name)
            key_path_with_ext = os.path.join(ssh_key_folder, f"{key_name}.pem")
            
            # Check if either path exists, prefer the one without extension if both exist
            if os.path.exists(key_path_without_ext) and os.path.isfile(key_path_without_ext):
                return key_path_without_ext
            elif os.path.exists(key_path_with_ext) and os.path.isfile(key_path_with_ext):
                return key_path_with_ext
        
        # If not found in any folder, return the first folder + key_name as default
        # (user can adjust if needed)
        if ssh_key_folders:
            return os.path.join(ssh_key_folders[0], key_name)
        
        # Fallback to ~/.ssh
        ssh_dir = os.path.expanduser("~/.ssh")
        return os.path.join(ssh_dir, key_name)

    def _generate_connection_info(self, connection_type: str, local_port: int, remote_port: int, instance_id: Optional[str] = None, key_name: Optional[str] = None, remote_host: Optional[str] = None) -> Dict[str, str]:
        """Generate connection instructions based on connection type."""
        if connection_type == "ssh":
            # For SSH, provide connection command
            # Default username varies by OS, but common ones are ec2-user, ubuntu, admin
            # Include options to skip host key checking
            ssh_options = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
            info = {
                "type": "ssh",
                "instruction": f"Connect via SSH to localhost:{local_port}",
                "command": f"ssh {ssh_options} -p {local_port} ec2-user@127.0.0.1",
                "note": "Replace 'ec2-user' with appropriate username (ubuntu, admin, etc.)",
                "ip": "127.0.0.1",
                "port": str(local_port),
                "user": "ec2-user"
            }
            if key_name and key_name != "N/A":
                info["key_name"] = key_name
                
                # Construct SSH key path
                key_path = self._construct_ssh_key_path(key_name)
                if key_path:
                    # Update command with -i flag and SSH options
                    info["command"] = f"ssh {ssh_options} -i {key_path} -p {local_port} ec2-user@127.0.0.1"
                    # Add full command with key path
                    info["ssh_command_with_key"] = info["command"]
                else:
                    # If key path couldn't be constructed, still add the field but without -i
                    info["ssh_command_with_key"] = info["command"]
            else:
                # No key name available
                info["ssh_command_with_key"] = info["command"]
            return info
        elif connection_type == "rdp":
            # For RDP, provide connection address
            info = {
                "type": "rdp",
                "instruction": f"Connect via RDP to localhost:{local_port}",
                "address": f"127.0.0.1:{local_port}",
                "note": "Use your RDP client (mstsc, Remote Desktop, etc.) to connect",
                "ip": "127.0.0.1",
                "port": str(local_port),
                "user": "Administrator",
                "instance_id": instance_id  # Store instance_id for password retrieval
            }
            if key_name and key_name != "N/A":
                info["key_name"] = key_name
            return info
        elif connection_type == "remote_host_port":
            # For remote host port forwarding, include remote host info
            remote_target = f"{remote_host}:{remote_port}" if remote_host else str(remote_port)
            info = {
                "type": "remote_host_port",
                "instruction": f"Port forwarding active on localhost:{local_port} -> {remote_target}",
                "local_address": f"127.0.0.1:{local_port}",
                "remote_port": str(remote_port),
                "remote_host": remote_host,
                "ip": "127.0.0.1",
                "port": str(local_port)
            }
            if key_name and key_name != "N/A":
                info["key_name"] = key_name
            return info
        else:
            # For custom ports (local port forwarding), provide generic info
            # Note: SSH key information is not included for custom ports
            info = {
                "type": "custom_port" if connection_type == "custom_port" else "port_forward",
                "instruction": f"Port forwarding active on localhost:{local_port} -> remote:{remote_port}",
                "local_address": f"127.0.0.1:{local_port}",
                "remote_port": str(remote_port),
                "ip": "127.0.0.1",
                "port": str(local_port)
            }
            # Don't include key_name for custom ports
            return info


    def _start_port_forward(self, instance_id: str, remote_port: int, remote_host: Optional[str] = None, connection_type: str = "port_forward", preferred_local_port: Optional[int] = None) -> Dict[str, Any]:
        """
        Start a port forwarding session.
        
        Args:
            instance_id: EC2 instance ID
            remote_port: Port on the instance to forward
            remote_host: Optional remote host (for forwarding to another host through the instance)
            connection_type: Type of connection (ssh, rdp, port_forward, etc.)
            preferred_local_port: Optional preferred local port (if provided and available, will use it)
        """
        start = getattr(self.preferences, "port_range_start", 60000)
        end = getattr(self.preferences, "port_range_end", 60100)
        
        # Determine local port
        if preferred_local_port is not None:
            # If a preferred local port is provided, try to use it
            if _is_port_free(preferred_local_port):
                local_port = preferred_local_port
                logger.info(f"Using preferred local port {preferred_local_port} for {connection_type} connection")
            else:
                logger.info(f"Preferred local port {preferred_local_port} not available, using port from range for {connection_type} connection")
                local_port = _in_range_free_port(start, end)
        elif connection_type in ("ssh", "rdp", "custom_port"):
            # For SSH, RDP, and custom ports, try to use the same local port as remote port first
            # If not available, fall back to port range
            if _is_port_free(remote_port):
                local_port = remote_port
                logger.info(f"Using same port as remote ({remote_port}) for {connection_type} connection")
            else:
                logger.info(f"Port {remote_port} not available, using port from range for {connection_type} connection")
                local_port = _in_range_free_port(start, end)
        else:
            # For other port forwarding types, use port range
            local_port = _in_range_free_port(start, end)

        _require("aws", "the AWS CLI v2")
        _require("session-manager-plugin", "the AWS Session Manager Plugin")

        profile = self._profile or "default"
        region = self._region

        # Build command as list to avoid command injection
        cmd_list = ["aws", "ssm", "start-session", "--target", instance_id]
        
        if remote_host:
            doc = "AWS-StartPortForwardingSessionToRemoteHost"
            cmd_list.extend([
                "--document-name", doc,
                "--parameters", f"host={remote_host},portNumber={remote_port},localPortNumber={local_port}"
            ])
        else:
            doc = "AWS-StartPortForwardingSession"
            cmd_list.extend([
                "--document-name", doc,
                "--parameters", f"portNumber={remote_port},localPortNumber={local_port}"
            ])
        
        if region:
            cmd_list.extend(["--region", region])
        if profile and profile != "default":
            cmd_list.extend(["--profile", profile])

        # Build command string for user display
        cmd_str = " ".join(f'"{arg}"' if " " in arg else arg for arg in cmd_list)

        # Spawn the port forwarding process in the background
        proc = self._spawn_background_process(cmd_list)
        
        # Get key name from instance details
        key_name = None
        try:
            instance_details = self.instance_details(instance_id)
            key_name = instance_details.get("key_name")
        except Exception as e:
            logger.warning(f"Could not retrieve key name for instance {instance_id}: {e}")
        
        # Generate connection instructions based on type
        # Pass remote_host for connection info generation if needed
        connection_info = self._generate_connection_info(connection_type, local_port, remote_port, instance_id, key_name, remote_host)
        
        cid = str(uuid.uuid4())
        self._connections[cid] = Connection(
            cid, 
            proc,  # Track the actual process
            cmd_str,
            {
                "instance_id": instance_id, 
                "local_port": local_port,
                "remote_port": remote_port,
                "remote_host": remote_host,
                "type": connection_type,
                "key_name": key_name  # Store key_name for later retrieval
            }
        )
        
        logger.info(f"Started {connection_type} port forwarding {cid} on local port {local_port}")
        result = {
            "connection_id": cid, 
            "local_port": local_port,
            "remote_port": remote_port,
            "command": cmd_str,
            "connection_info": connection_info
        }
        # Include remote_host if present
        if remote_host:
            result["remote_host"] = remote_host
        return result

    def start_ssh(self, instance_id: str) -> Dict[str, Any]:
        """Start SSH connection via port forwarding to port 22."""
        return self._start_port_forward(instance_id, 22, connection_type="ssh")


    def start_rdp(self, instance_id: str) -> Dict[str, Any]:
        """Start RDP connection via port forwarding to port 3389."""
        return self._start_port_forward(instance_id, 3389, connection_type="rdp")

    def start_custom_port(self, instance_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        remote_port = int(data.get("remote_port", 22))
        local_port = data.get("local_port")  # Optional
        if local_port is not None:
            local_port = int(local_port)
        # Custom ports always forward to the instance itself (no remote_host)
        return self._start_port_forward(instance_id, remote_port, remote_host=None, connection_type="custom_port", preferred_local_port=local_port)

    # ------------- Windows Password Retrieval -------------

    def get_windows_password_data(self, instance_id: str) -> Dict[str, Any]:
        """Get encrypted password data for a Windows instance."""
        ec2 = self.session().client("ec2")
        try:
            response = ec2.get_password_data(InstanceId=instance_id)
            return {
                "password_data": response.get("PasswordData", ""),
                "timestamp": response.get("Timestamp", "").isoformat() if response.get("Timestamp") else None
            }
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "InvalidInstanceID.NotFound":
                raise ValueError(f"Instance {instance_id} not found")
            elif error_code == "InvalidInstanceState":
                raise ValueError(f"Instance {instance_id} is not in a valid state for password retrieval")
            else:
                raise ValueError(f"Failed to retrieve password data: {str(e)}")

    def decrypt_windows_password(self, encrypted_password: str, pem_key_content: str) -> str:
        """Decrypt Windows password using PEM private key."""
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("cryptography library is required for password decryption. Install it with: pip install cryptography")
        
        if not encrypted_password:
            raise ValueError("No encrypted password data available")
        
        try:
            # Load the PEM private key
            private_key = load_pem_private_key(
                pem_key_content.encode('utf-8'),
                password=None,
                backend=default_backend()
            )
            
            # Decode the base64 encrypted password
            encrypted_bytes = base64.b64decode(encrypted_password)
            
            # Decrypt using RSA private key
            decrypted_password = private_key.decrypt(
                encrypted_bytes,
                padding.PKCS1v15()
            )
            
            return decrypted_password.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Failed to decrypt password: {str(e)}")

    # ------------- RDP Client Launcher -------------

    def launch_rdp_client(self, ip: str, port: int, username: str, password: Optional[str] = None) -> Dict[str, Any]:
        """
        Launch the system RDP client with connection parameters.
        
        Args:
            ip: IP address to connect to (typically 127.0.0.1 for port forwarding)
            port: Port number (local port from port forwarding)
            username: Username for RDP connection
            password: Optional password for RDP connection
        
        Returns:
            Dict with success status and message
        """
        try:
            system = platform.system()
            
            if system == "Windows":
                return self._launch_rdp_windows(ip, port, username, password)
            elif system == "Darwin":  # macOS
                return self._launch_rdp_macos(ip, port, username, password)
            elif system == "Linux":
                return self._launch_rdp_linux(ip, port, username, password)
            else:
                raise RuntimeError(f"Unsupported operating system: {system}")
        except Exception as e:
            logger.error(f"Failed to launch RDP client: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def _launch_rdp_windows(self, ip: str, port: int, username: str, password: Optional[str] = None) -> Dict[str, Any]:
        """Launch RDP client on Windows using mstsc.exe"""
        try:
            # Note: mstsc.exe doesn't support password via command line for security reasons
            # We'll launch with username and let user enter password, or use RDP file
            # For simplicity, we'll use command line with username
            cmd = ["mstsc.exe", f"/v:{ip}:{port}"]
            
            # Add username if provided (mstsc will prompt for password)
            # Note: /u parameter exists but password must be entered manually for security
            if username:
                cmd.extend(["/u", username])
            
            # Windows-specific creation flags
            kwargs = {}
            if os.name == "nt":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            
            subprocess.Popen(cmd, **kwargs)
            
            message = f"RDP client launched connecting to {ip}:{port}"
            if password:
                message += " (password will need to be entered in RDP client)"
            else:
                message += " (enter credentials when prompted)"
            
            return {
                "success": True,
                "message": message
            }
        except Exception as e:
            raise RuntimeError(f"Failed to launch Windows RDP client: {e}")

    def _launch_rdp_macos(self, ip: str, port: int, username: str, password: Optional[str] = None) -> Dict[str, Any]:
        """Launch RDP client on macOS using Windows App with RDP file"""
        try:
            # Create a temporary RDP file
            rdp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.rdp', delete=False)
            rdp_file_path = rdp_file.name
            
            try:
                # Write RDP file content (minimal, following user's example)
                rdp_file.write(f"full address:s:{ip}:{port}\n")
                rdp_file.write(f"username:s:{username}\n")
                
                # Add password if provided (RDP file format - password is stored encrypted)
                # Note: Some RDP clients may prompt for password even if stored
                if password:
                    # RDP file password format: password 51:b:<encrypted_password>
                    # For simplicity, we'll use the plain password format that some clients accept
                    # Windows App may handle this differently
                    rdp_file.write(f"password 51:b:{password}\n")
                
                rdp_file.close()
                
                # Try different possible app names for Windows App
                app_names = [
                    "Windows App",
                    "Windows App.app",
                    "/Applications/Windows App.app",
                    "Microsoft Remote Desktop",
                    "Microsoft Remote Desktop.app",
                    "/Applications/Microsoft Remote Desktop.app",
                ]
                
                # Try to launch with Windows App
                launched = False
                last_error = None
                
                for app_name in app_names:
                    try:
                        if app_name.startswith("/"):
                            # Full path
                            cmd = ["open", "-a", app_name, rdp_file_path]
                        else:
                            # App name
                            cmd = ["open", "-a", app_name, rdp_file_path]
                        
                        result = subprocess.run(cmd, capture_output=True, timeout=5)
                        if result.returncode == 0:
                            launched = True
                            break
                    except Exception as e:
                        last_error = e
                        continue
                
                if not launched:
                    # Fallback: try using the rdp:// URL scheme directly
                    try:
                        rdp_url = f"rdp://{username}@{ip}:{port}"
                        cmd = ["open", rdp_url]
                        subprocess.Popen(cmd)
                        # Clean up temp file
                        try:
                            os.unlink(rdp_file_path)
                        except Exception:
                            pass
                        return {
                            "success": True,
                            "message": f"RDP connection opened to {ip}:{port} (using default RDP handler)"
                        }
                    except Exception as e:
                        # Clean up temp file
                        try:
                            os.unlink(rdp_file_path)
                        except Exception:
                            pass
                        raise RuntimeError(f"Failed to launch RDP client. Windows App may not be installed. Error: {e}")
                
                # Note: We don't delete the temp file immediately as the RDP client needs to read it
                # The file will be cleaned up by the OS temp file cleanup or can be manually deleted later
                
                return {
                    "success": True,
                    "message": f"Windows App launched connecting to {ip}:{port}",
                    "rdp_file": rdp_file_path  # Return path for potential cleanup
                }
            except Exception as e:
                # Clean up temp file on error
                try:
                    os.unlink(rdp_file_path)
                except Exception:
                    pass
                raise
        except Exception as e:
            raise RuntimeError(f"Failed to launch Windows App: {e}")

    def _launch_rdp_linux(self, ip: str, port: int, username: str, password: Optional[str] = None) -> Dict[str, Any]:
        """Launch RDP client on Linux"""
        try:
            # Try xfreerdp first, then remmina
            if shutil.which("xfreerdp"):
                cmd = ["xfreerdp", f"/v:{ip}:{port}", f"/u:{username}"]
                if password:
                    cmd.append(f"/p:{password}")
                cmd.append("/cert:ignore")  # Ignore certificate warnings
                subprocess.Popen(cmd)
                return {
                    "success": True,
                    "message": f"RDP client (xfreerdp) launched connecting to {ip}:{port}"
                }
            elif shutil.which("remmina"):
                # Remmina can use command line or create a connection file
                # For simplicity, we'll use command line with connection string
                conn_string = f"rdp://{username}@{ip}:{port}"
                if password:
                    conn_string = f"rdp://{username}:{password}@{ip}:{port}"
                cmd = ["remmina", "-c", conn_string]
                subprocess.Popen(cmd)
                return {
                    "success": True,
                    "message": f"RDP client (remmina) launched connecting to {ip}:{port}"
                }
            else:
                raise RuntimeError("No RDP client found. Please install xfreerdp or remmina.")
        except Exception as e:
            raise RuntimeError(f"Failed to launch Linux RDP client: {e}")


    # ------------- Lifecycle -------------

    def terminate(self, connection_id: str):
        conn = self._connections.pop(connection_id, None)
        if conn and conn.proc:
            try:
                pid = conn.proc.pid
                logger.info(f"Terminating connection {connection_id} (PID: {pid})")
                
                # Use kill_process_tree to kill the entire process tree
                # This is important because processes are spawned with start_new_session=True
                from .utils import kill_process_tree
                if kill_process_tree(pid):
                    logger.info(f"Successfully terminated connection {connection_id} and all child processes")
                else:
                    # Fallback to standard termination if kill_process_tree fails
                    logger.warning(f"kill_process_tree failed, using fallback termination for {connection_id}")
                    conn.proc.terminate()
                    try:
                        conn.proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        conn.proc.kill()
                        conn.proc.wait()
            except Exception as e:
                logger.warning(f"Error terminating connection {connection_id}: {e}", exc_info=True)
                # Try to kill if terminate failed
                try:
                    if conn.proc.poll() is None:
                        conn.proc.kill()
                except Exception:
                    pass

    def terminate_all(self):
        """Terminate all active connections."""
        connection_ids = list(self._connections.keys())
        if not connection_ids:
            logger.info("No active connections to terminate")
            return
            
        logger.info(f"Terminating all {len(connection_ids)} active connections")
        for connection_id in connection_ids:
            try:
                self.terminate(connection_id)
            except Exception as e:
                logger.warning(f"Error terminating connection {connection_id} during cleanup: {e}", exc_info=True)
        
        # Verify all connections are terminated
        remaining = len(self._connections)
        if remaining > 0:
            logger.warning(f"Warning: {remaining} connections still remain after cleanup attempt")
        else:
            logger.info("All connections terminated successfully")

    def active_connections(self) -> List[Dict[str, Any]]:
        """Return all active connections with their status."""
        alive = []
        for cid, conn in list(self._connections.items()):
            connection_data = {
                "connection_id": cid, 
                "command": conn.command,
                **conn.meta
            }
            
            # Generate connection info if we have the connection type
            if conn.meta.get("type"):
                # Get key_name from stored connection info if available, otherwise fetch it
                key_name = None
                if conn.meta.get("key_name"):
                    key_name = conn.meta.get("key_name")
                elif conn.meta.get("instance_id"):
                    try:
                        instance_details = self.instance_details(conn.meta.get("instance_id"))
                        key_name = instance_details.get("key_name")
                    except Exception:
                        pass
                
                connection_data["connection_info"] = self._generate_connection_info(
                    conn.meta["type"],
                    conn.meta.get("local_port", 0),
                    conn.meta.get("remote_port", 0),
                    conn.meta.get("instance_id"),
                    key_name,
                    conn.meta.get("remote_host")
                )
            
            if conn.proc is None:
                # No process tracked - connection info only
                alive.append(connection_data)
            else:
                # Check if process is still running
                try:
                    if conn.proc.poll() is None:
                        # Process is still running
                        alive.append(connection_data)
                    else:
                        # Process has terminated
                        logger.info(f"Connection {cid} process terminated (exit code: {conn.proc.returncode})")
                        self._connections.pop(cid, None)
                except Exception as e:
                    logger.warning(f"Error checking connection {cid}: {e}")
                    # Remove problematic connection
                    self._connections.pop(cid, None)
        return alive
