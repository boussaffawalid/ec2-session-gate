import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

PREF_PATH = Path.home() / ".config" / "ssm_manager" / "preferences.json"
PREF_PATH.parent.mkdir(parents=True, exist_ok=True)

DEFAULTS = {
    "port_range": {"start": 60000, "end": 60100},
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
        return cls(
            port_range_start=int(pr.get("start", DEFAULTS["port_range"]["start"])),
            port_range_end=int(pr.get("end", DEFAULTS["port_range"]["end"])),
            logging_level=str(lg.get("level", DEFAULTS["logging"]["level"])),
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
        PREF_PATH.parent.mkdir(parents=True, exist_ok=True)
        PREF_PATH.write_text(json.dumps(self.to_dict(), indent=2))
