import json
import platform
import os
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

PREF_PATH = Path.home() / ".config" / "ec2-session-gate" / "preferences.json"
PREF_PATH.parent.mkdir(parents=True, exist_ok=True)

def _get_default_port_range():
    """Get OS-specific default port range to avoid ephemeral port conflicts.
    
    Ephemeral port ranges:
    - Windows: 49152-65535
    - Linux: 32768-60999 (varies by distro)
    - macOS: 49152-65535
    
    Returns:
        dict: Port range with 'start' and 'end' keys
    """
    system = platform.system().lower()
    
    if system == "windows":
        # Windows: Use range below ephemeral ports (49152-65535)
        return {"start": 40000, "end": 40100}
    elif system in ("linux", "darwin"):  # darwin is macOS
        # Linux/macOS: Use range above Linux ephemeral ports (32768-60999)
        # This is safe for macOS too since 61000+ is above its ephemeral range
        return {"start": 61000, "end": 61100}
    else:
        # Fallback for other systems
        return {"start": 60000, "end": 60100}

DEFAULTS = {
    "port_range": _get_default_port_range(),
    "logging": {"level": "INFO", "format": "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"},
    "aws": {"profile": None, "region": None},
    "ssh_key_folder": None
}

@dataclass
class Preferences:
    port_range_start: int = DEFAULTS["port_range"]["start"]
    port_range_end: int = DEFAULTS["port_range"]["end"]
    logging_level: str = DEFAULTS["logging"]["level"]
    logging_format: str = DEFAULTS["logging"]["format"]
    last_profile: Optional[str] = None
    last_region: Optional[str] = None
    ssh_key_folder: Optional[str] = None

    @classmethod
    def load(cls):
        if PREF_PATH.exists():
            try:
                data = json.loads(PREF_PATH.read_text())
                return cls.from_dict(data)
            except Exception:
                pass
        return cls()

    @classmethod
    def from_dict(cls, data):
        pr = data.get("port_range", {})
        lg = data.get("logging", {})
        aws = data.get("aws", {})
        
        # Validate and set port range
        from .constants import MIN_PORT, MAX_PORT
        port_start = int(pr.get("start", DEFAULTS["port_range"]["start"]))
        port_end = int(pr.get("end", DEFAULTS["port_range"]["end"]))
        
        # Validate port range
        if port_start < MIN_PORT or port_start > MAX_PORT:
            logger.warning(f"Invalid port_range_start {port_start}, using default")
            port_start = DEFAULTS["port_range"]["start"]
        if port_end < MIN_PORT or port_end > MAX_PORT:
            logger.warning(f"Invalid port_range_end {port_end}, using default")
            port_end = DEFAULTS["port_range"]["end"]
        if port_start >= port_end:
            logger.warning(f"Invalid port range {port_start}-{port_end}, using defaults")
            port_start = DEFAULTS["port_range"]["start"]
            port_end = DEFAULTS["port_range"]["end"]
        
        # Validate logging level
        from .constants import VALID_LOG_LEVELS
        log_level = str(lg.get("level", DEFAULTS["logging"]["level"])).upper()
        if log_level not in VALID_LOG_LEVELS:
            logger.warning(f"Invalid logging level {log_level}, using default")
            log_level = DEFAULTS["logging"]["level"]
        
        return cls(
            port_range_start=port_start,
            port_range_end=port_end,
            logging_level=log_level,
            logging_format=str(lg.get("format", DEFAULTS["logging"]["format"])),
            last_profile=aws.get("profile") or None,
            last_region=aws.get("region") or None,
            ssh_key_folder=data.get("ssh_key_folder") or None,
        )

    def to_dict(self):
        result = {
            "port_range": {"start": self.port_range_start, "end": self.port_range_end},
            "logging": {"level": self.logging_level, "format": self.logging_format},
        }
        # Only include AWS settings if they have values
        aws_data = {}
        if self.last_profile:
            aws_data["profile"] = self.last_profile
        if self.last_region:
            aws_data["region"] = self.last_region
        if aws_data:
            result["aws"] = aws_data
        # Include SSH key folder if set
        if self.ssh_key_folder:
            result["ssh_key_folder"] = self.ssh_key_folder
        return result

    def save(self):
        """Save preferences to file with appropriate permissions."""
        from .constants import PREF_DIR_PERMISSIONS, PREF_FILE_PERMISSIONS, VALID_LOG_LEVELS
        
        PREF_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Set directory permissions (not world-readable)
        try:
            os.chmod(PREF_PATH.parent, PREF_DIR_PERMISSIONS)
        except Exception:
            pass  # Ignore permission errors on some systems
        
        # Write preferences
        PREF_PATH.write_text(json.dumps(self.to_dict(), indent=2))
        
        # Set file permissions (not world-readable)
        try:
            os.chmod(PREF_PATH, PREF_FILE_PERMISSIONS)
        except Exception:
            pass  # Ignore permission errors on some systems
