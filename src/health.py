import platform, shutil, boto3
from dataclasses import dataclass
from typing import Dict

@dataclass
class HealthReport:
    aws_cli: bool
    session_manager_plugin: bool
    aws_credentials: bool
    os: str
    version: str = "1.0.0"

    def to_dict(self) -> Dict:
        return {
            "aws_cli": self.aws_cli,
            "session_manager_plugin": self.session_manager_plugin,
            "aws_credentials": self.aws_credentials,
            "os": self.os,
            "version": self.version,
        }

def check_health() -> HealthReport:
    aws_cli = shutil.which("aws") is not None
    smp = shutil.which("session-manager-plugin") is not None
    creds_ok = False
    try:
        sess = boto3.session.Session()
        creds = sess.get_credentials()
        creds_ok = creds is not None
    except Exception:
        creds_ok = False
    return HealthReport(
        aws_cli=aws_cli,
        session_manager_plugin=smp,
        aws_credentials=creds_ok,
        os=platform.system(),
    )
