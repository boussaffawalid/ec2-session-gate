import platform
import shutil
import boto3
import logging
from dataclasses import dataclass
from typing import Dict, Optional
from .version import __version__

logger = logging.getLogger(__name__)

@dataclass
class HealthReport:
    aws_cli: bool
    session_manager_plugin: bool
    aws_credentials: bool
    os: str
    version: str = __version__
    aws_cli_version: Optional[str] = None
    errors: Optional[Dict[str, str]] = None

    def to_dict(self) -> Dict:
        result = {
            "aws_cli": self.aws_cli,
            "session_manager_plugin": self.session_manager_plugin,
            "aws_credentials": self.aws_credentials,
            "os": self.os,
            "version": self.version,
        }
        if self.aws_cli_version:
            result["aws_cli_version"] = self.aws_cli_version
        if self.errors:
            result["errors"] = self.errors
        return result

def check_health() -> HealthReport:
    """
    Check system health and dependencies.
    
    Returns:
        HealthReport with status of all dependencies
    """
    errors = {}
    aws_cli = shutil.which("aws") is not None
    aws_cli_version = None
    
    if aws_cli:
        try:
            import subprocess
            result = subprocess.run(
                ["aws", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                aws_cli_version = result.stdout.strip()
        except Exception as e:
            logger.debug(f"Could not get AWS CLI version: {e}")
            errors["aws_cli_version"] = str(e)
    
    smp = shutil.which("session-manager-plugin") is not None
    
    creds_ok = False
    creds_error = None
    try:
        sess = boto3.session.Session()
        creds = sess.get_credentials()
        creds_ok = creds is not None
        if not creds_ok:
            creds_error = "No AWS credentials found"
    except Exception as e:
        creds_error = str(e)
        logger.debug(f"AWS credentials check failed: {e}")
    
    if creds_error:
        errors["aws_credentials"] = creds_error
    
    # Get version - try to get from installed package, fallback to source version
    try:
        import importlib.metadata
        try:
            version = importlib.metadata.version("ec2-session-gate")
        except importlib.metadata.PackageNotFoundError:
            version = __version__
    except ImportError:
        try:
            import pkg_resources
            version = pkg_resources.get_distribution("ec2-session-gate").version
        except Exception:
            version = __version__
    except Exception:
        version = __version__
    
    return HealthReport(
        aws_cli=aws_cli,
        session_manager_plugin=smp,
        aws_credentials=creds_ok,
        os=platform.system(),
        version=version,
        aws_cli_version=aws_cli_version,
        errors=errors if errors else None
    )
