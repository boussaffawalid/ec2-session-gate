import logging
from functools import wraps
from flask import Blueprint, jsonify, request
from botocore.exceptions import ClientError

from .preferences_handler import Preferences
from .aws_manager import AWSManager
from .utils import (
    create_success_response, 
    create_error_response,
    validate_instance_id,
    validate_connection_id,
    validate_port,
    validate_port_range,
    validate_remote_host
)
from .health import check_health

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__)
prefs = Preferences.load()
aws_manager = AWSManager(prefs)

# Request logging middleware
@api_bp.before_request
def log_request():
    """Log API requests for debugging and monitoring."""
    logger.debug(f"API Request: {request.method} {request.path} from {request.remote_addr}")

# Decorator for input validation
def validate_instance_id_param(f):
    """Decorator to validate instance_id parameter."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        instance_id = kwargs.get('instance_id')
        if instance_id:
            is_valid, error_msg = validate_instance_id(instance_id)
            if not is_valid:
                return create_error_response(error_msg), 400
        return f(*args, **kwargs)
    return decorated_function

def validate_connection_id_param(f):
    """Decorator to validate connection_id parameter."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        connection_id = kwargs.get('connection_id')
        if connection_id:
            is_valid, error_msg = validate_connection_id(connection_id)
            if not is_valid:
                return create_error_response(error_msg), 400
        return f(*args, **kwargs)
    return decorated_function

@api_bp.get("/profiles")
def get_profiles():
    try:
        return jsonify(aws_manager.list_profiles())
    except Exception as e:
        return create_error_response(str(e)), 500

@api_bp.get("/regions")
def get_regions():
    """Return enabled AWS regions for the selected profile."""
    try:
        profile = request.args.get("profile", "default")
        session = aws_manager.session(profile=profile)
        #  Always specify a fallback region (for profiles without a region)
        ec2 = session.client("ec2", region_name="us-east-1")

        resp = ec2.describe_regions(AllRegions=False)
        regions = sorted([r["RegionName"] for r in resp["Regions"]])
        return jsonify({"ok": True, "data": regions})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@api_bp.post("/connect")
def connect_to_aws():
    data = request.get_json() or {}
    profile = data.get("profile")
    region = data.get("region")
    
    if not profile or not region:
        return create_error_response("Profile and region are required"), 400
    
    try:
        account_info = aws_manager.connect(profile, region)
        
        # Save profile and region to preferences
        prefs = Preferences.load()
        prefs.last_profile = profile
        prefs.last_region = region
        prefs.save()
        logger.info(f"Saved last connection: profile={profile}, region={region}")
        
        return create_success_response({
            "account_id": account_info["account_id"],
            "account_alias": account_info.get("account_alias")
        })
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        
        if error_code == "AuthFailure" or "credential" in error_message.lower():
            error_msg = f"Invalid AWS credentials for profile '{profile}'. Please configure your AWS credentials."
        else:
            error_msg = f"AWS Error ({error_code}): {error_message}"
        
        logger.error(f"Connection failed for profile '{profile}', region '{region}': {error_msg}")
        return create_error_response(error_msg), 400
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Connection failed for profile '{profile}', region '{region}': {error_msg}", exc_info=True)
        
        # Check if it's a credential-related error
        if "credential" in error_msg.lower() or "auth" in error_msg.lower() or "access" in error_msg.lower():
            error_msg = f"Invalid AWS credentials for profile '{profile}'. Please configure your AWS credentials."
        
        return create_error_response(error_msg), 400

@api_bp.get("/instances")
def get_instances():
    try:
        return jsonify(aws_manager.list_instances())
    except Exception as e:
        return create_error_response(str(e)), 500

@api_bp.post("/ssh/<instance_id>")
@validate_instance_id_param
def start_ssh_session(instance_id):
    data = request.get_json() or {}
    try:
        result = aws_manager.start_ssh(instance_id)
        logger.info(f"SSH session started for instance {instance_id}, connection_id: {result.get('connection_id')}")
        return create_success_response(result)
    except Exception as e:
        logger.error(f"Failed to start SSH session for instance {instance_id}: {e}", exc_info=True)
        return create_error_response(str(e)), 400

@api_bp.post("/rdp/<instance_id>")
@validate_instance_id_param
def start_rdp_session(instance_id):
    data = request.get_json() or {}
    try:
        payload = aws_manager.start_rdp(instance_id)
        logger.info(f"RDP session started for instance {instance_id}, connection_id: {payload.get('connection_id')}")
        return create_success_response(payload)
    except Exception as e:
        logger.error(f"Failed to start RDP session for instance {instance_id}: {e}", exc_info=True)
        return create_error_response(str(e)), 400

@api_bp.post("/custom-port/<instance_id>")
@validate_instance_id_param
def start_custom_port_forward(instance_id):
    data = request.get_json() or {}
    try:
        # Validate remote port
        remote_port = data.get("remote_port")
        if remote_port is None:
            return create_error_response("remote_port is required"), 400
        
        try:
            remote_port = int(remote_port)
        except (ValueError, TypeError):
            return create_error_response("remote_port must be a valid integer"), 400
        
        if not validate_port(remote_port):
            return create_error_response(f"remote_port {remote_port} is out of valid range (1-65535)"), 400
        
        # Validate local port if provided
        local_port = data.get("local_port")
        if local_port is not None:
            try:
                local_port = int(local_port)
            except (ValueError, TypeError):
                return create_error_response("local_port must be a valid integer"), 400
            
            if not validate_port(local_port):
                return create_error_response(f"local_port {local_port} is out of valid range (1-65535)"), 400
        
        # Validate remote_host if provided
        remote_host = data.get("remote_host")
        if remote_host and not validate_remote_host(remote_host):
            return create_error_response(f"Invalid remote_host format: {remote_host}"), 400
        
        payload = aws_manager.start_custom_port(instance_id, data)
        logger.info(f"Custom port forwarding started for instance {instance_id}, connection_id: {payload.get('connection_id')}")
        return create_success_response(payload)
    except Exception as e:
        logger.error(f"Failed to start custom port forwarding for instance {instance_id}: {e}", exc_info=True)
        return create_error_response(str(e)), 400

@api_bp.post("/terminate-connection/<connection_id>")
@validate_connection_id_param
def terminate_connection(connection_id):
    try:
        aws_manager.terminate(connection_id)
        logger.info(f"Connection {connection_id} terminated")
        return create_success_response({})
    except Exception as e:
        logger.error(f"Failed to terminate connection {connection_id}: {e}", exc_info=True)
        return create_error_response(str(e)), 400

@api_bp.post("/terminate-all-connections")
def terminate_all_connections():
    """Terminate all active connections."""
    try:
        aws_manager.terminate_all()
        return create_success_response({"message": "All connections terminated"})
    except Exception as e:
        return create_error_response(str(e)), 400

@api_bp.get("/active-connections")
def get_active_connections():
    try:
        return jsonify(aws_manager.active_connections())
    except Exception as e:
        return create_error_response(str(e)), 500

@api_bp.get("/preferences")
def get_preferences():
    return jsonify(Preferences.load().to_dict())

@api_bp.post("/preferences")
def set_preferences():
    data = request.get_json() or {}
    
    try:
        # Validate port range if provided
        if "port_range" in data:
            pr = data.get("port_range", {})
            start = pr.get("start")
            end = pr.get("end")
            
            if start is not None or end is not None:
                from .utils import validate_port_range
                # Use existing preferences as defaults if not provided
                existing_prefs = Preferences.load()
                start = start if start is not None else existing_prefs.port_range_start
                end = end if end is not None else existing_prefs.port_range_end
                
                is_valid, error_msg = validate_port_range(start, end)
                if not is_valid:
                    logger.warning(f"Invalid port range provided: {error_msg}")
                    return create_error_response(f"Invalid port range: {error_msg}"), 400
        
        # Validate logging level if provided
        if "logging" in data:
            from .constants import VALID_LOG_LEVELS
            lg = data.get("logging", {})
            log_level = lg.get("level")
            if log_level:
                if log_level.upper() not in VALID_LOG_LEVELS:
                    return create_error_response(f"Invalid logging level: {log_level}. Valid levels: {', '.join(VALID_LOG_LEVELS)}"), 400
        
        # Load existing preferences to preserve AWS settings if not provided
        existing_prefs = Preferences.load()
        
        # Create new preferences from provided data
        p = Preferences.from_dict(data)
        
        # Preserve AWS settings if not in the request (they're saved separately via /api/connect)
        if "aws" not in data:
            p.last_profile = existing_prefs.last_profile
            p.last_region = existing_prefs.last_region
        
        p.save()
        
        # Reload preferences in aws_manager to use updated values
        aws_manager.preferences = Preferences.load()
        
        logger.info(f"Saved preferences: port_range={p.port_range_start}-{p.port_range_end}, logging_level={p.logging_level}")
        return create_success_response(p.to_dict())
    except ValueError as e:
        logger.error(f"Invalid preferences data: {e}", exc_info=True)
        return create_error_response(f"Invalid preferences: {str(e)}"), 400
    except Exception as e:
        logger.error(f"Error saving preferences: {e}", exc_info=True)
        return create_error_response(f"Failed to save preferences: {str(e)}"), 500

@api_bp.get("/last-connection")
def get_last_aws_connection():
    """Return the last used profile and region from preferences."""
    try:
        prefs = Preferences.load()
        return jsonify({
            "profile": prefs.last_profile or "",
            "region": prefs.last_region or ""
        })
    except Exception as e:
        logger.error(f"Error loading last connection: {e}")
        return jsonify({"profile": "", "region": ""})

@api_bp.get("/instance-details/<instance_id>")
@validate_instance_id_param
def get_instance_details(instance_id):
    try:
        details = aws_manager.instance_details(instance_id)
        return jsonify(details)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "InvalidInstanceID.NotFound":
            logger.warning(f"Instance {instance_id} not found")
            return create_error_response(f"Instance {instance_id} not found"), 404
        logger.error(f"Error retrieving instance details for {instance_id}: {e}", exc_info=True)
        return create_error_response(f"AWS Error: {error_code}"), 400
    except Exception as e:
        logger.error(f"Error retrieving instance details for {instance_id}: {e}", exc_info=True)
        return create_error_response(str(e)), 400

@api_bp.get("/health")
def get_health_status():
    try:
        rep = check_health().to_dict()
        return jsonify(rep)
    except Exception as e:
        return create_error_response(str(e)), 500

@api_bp.get("/version")
def get_version():
    """Get application version information."""
    from .version import __version__ as fallback_version
    
    try:
        import importlib.metadata
        try:
            version = importlib.metadata.version("ec2-session-gate")
        except importlib.metadata.PackageNotFoundError:
            # Fallback to version from source if package not installed
            version = fallback_version
        return jsonify({"version": version})
    except ImportError:
        # Python < 3.8 fallback
        try:
            import pkg_resources
            version = pkg_resources.get_distribution("ec2-session-gate").version
        except Exception:
            version = fallback_version
        return jsonify({"version": version})
    except Exception as e:
        logger.error(f"Error retrieving version: {e}", exc_info=True)
        return jsonify({"version": fallback_version})  # Return fallback version on error

@api_bp.post("/rdp-client/connect")
def launch_rdp_client():
    """Launch RDP client with connection parameters."""
    data = request.get_json() or {}
    
    ip = data.get("ip")
    port = data.get("port")
    username = data.get("username")
    password = data.get("password")  # Optional
    
    if not ip or not port or not username:
        return create_error_response("IP, port, and username are required"), 400
    
    try:
        # Validate port is a valid integer
        port = int(port)
        if port < 1 or port > 65535:
            return create_error_response("Port must be between 1 and 65535"), 400
        
        result = aws_manager.launch_rdp_client(ip, port, username, password)
        
        if result.get("success"):
            return create_success_response({
                "message": result.get("message", "RDP client launched successfully")
            })
        else:
            return create_error_response(result.get("error", "Failed to launch RDP client")), 500
            
    except ValueError as e:
        return create_error_response(f"Invalid port number: {str(e)}"), 400
    except Exception as e:
        logger.error(f"Error launching RDP client: {e}", exc_info=True)
        return create_error_response(str(e)), 500

@api_bp.post("/windows-password/<instance_id>")
@validate_instance_id_param
def get_windows_password(instance_id):
    """Get and decrypt Windows instance password."""
    import os
    from pathlib import Path
    
    # Reload preferences to get latest SSH key folder setting
    current_prefs = Preferences.load()
    
    data = request.get_json() or {}
    pem_key_content = data.get("pem_key")
    key_name = data.get("key_name")
    
    # If no PEM key provided, try to auto-lookup from preferences
    if not pem_key_content and key_name:
        ssh_key_folder = current_prefs.ssh_key_folder
        if ssh_key_folder:
            # Support multiple directories separated by newlines or commas
            folder_strings = []
            for line in ssh_key_folder.split('\n'):
                folder_strings.extend([f.strip() for f in line.split(',') if f.strip()])
            
            # Remove duplicates
            seen = set()
            unique_folders = []
            for folder_str in folder_strings:
                if folder_str and folder_str not in seen:
                    seen.add(folder_str)
                    unique_folders.append(folder_str)
            
            # Try common key file names
            key_file_names = [
                key_name,
                f"{key_name}.pem",
                f"{key_name}.key",
                f"id_rsa_{key_name}",
                f"{key_name}_private.pem"
            ]
            
            # Search through all configured folders
            for folder_str in unique_folders:
                folder_path = Path(os.path.expanduser(folder_str))
                if folder_path.exists() and folder_path.is_dir():
                    for key_file_name in key_file_names:
                        key_file_path = folder_path / key_file_name
                        if key_file_path.exists() and key_file_path.is_file():
                            try:
                                pem_key_content = key_file_path.read_text()
                                logger.info(f"Auto-loaded SSH key from {key_file_path}")
                                break
                            except Exception as e:
                                logger.warning(f"Failed to read key file {key_file_path}: {e}")
                                continue
                    if pem_key_content:
                        break  # Found the key, stop searching
    
    if not pem_key_content:
        return create_error_response("PEM key is required for password decryption. Please provide a key or configure SSH key folder in preferences."), 400
    
    try:
        # Get encrypted password data
        password_data = aws_manager.get_windows_password_data(instance_id)
        
        if not password_data.get("password_data"):
            return create_error_response("No password data available for this instance. The instance may not be ready yet."), 400
        
        # Decrypt the password
        decrypted_password = aws_manager.decrypt_windows_password(
            password_data["password_data"],
            pem_key_content
        )
        
        return create_success_response({
            "password": decrypted_password,
            "timestamp": password_data.get("timestamp")
        })
    except ValueError as e:
        return create_error_response(str(e)), 400
    except Exception as e:
        logger.error(f"Error retrieving Windows password: {e}", exc_info=True)
        return create_error_response(str(e)), 500
