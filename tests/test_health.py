"""Tests for health check functionality in src/health.py"""
import pytest
import platform
from unittest.mock import patch, MagicMock
from src.health import HealthReport, check_health
from src.version import __version__


class TestHealthReport:
    """Tests for HealthReport dataclass"""
    
    def test_health_report_creation(self):
        """Test creating a health report"""
        report = HealthReport(
            aws_cli=True,
            session_manager_plugin=True,
            aws_credentials=True,
            os="Linux",
            version=__version__
        )
        
        assert report.aws_cli is True
        assert report.session_manager_plugin is True
        assert report.aws_credentials is True
        assert report.os == "Linux"
        assert report.version == __version__
    
    def test_health_report_to_dict(self):
        """Test converting health report to dictionary"""
        report = HealthReport(
            aws_cli=True,
            session_manager_plugin=False,
            aws_credentials=True,
            os="Darwin",
            version=__version__
        )
        
        result = report.to_dict()
        
        assert result == {
            "aws_cli": True,
            "session_manager_plugin": False,
            "aws_credentials": True,
            "os": "Darwin",
            "version": __version__
        }
    
    def test_health_report_default_version(self):
        """Test health report with default version"""
        report = HealthReport(
            aws_cli=True,
            session_manager_plugin=True,
            aws_credentials=True,
            os="Windows"
        )
        
        assert report.version == __version__


class TestCheckHealth:
    """Tests for check_health function"""
    
    @patch('src.health.shutil.which')
    @patch('src.health.boto3.session.Session')
    def test_check_health_all_ok(self, mock_session_class, mock_which):
        """Test health check when all dependencies are available"""
        mock_which.side_effect = lambda cmd: "/usr/bin/aws" if cmd == "aws" else "/usr/bin/session-manager-plugin"
        
        mock_session = MagicMock()
        mock_session.get_credentials.return_value = MagicMock()
        mock_session_class.return_value = mock_session
        
        report = check_health()
        
        assert report.aws_cli is True
        assert report.session_manager_plugin is True
        assert report.aws_credentials is True
        assert report.os == platform.system()
    
    @patch('src.health.shutil.which')
    @patch('src.health.boto3.session.Session')
    def test_check_health_missing_cli(self, mock_session_class, mock_which):
        """Test health check when AWS CLI is missing"""
        mock_which.side_effect = lambda cmd: None if cmd == "aws" else "/usr/bin/session-manager-plugin"
        
        mock_session = MagicMock()
        mock_session.get_credentials.return_value = MagicMock()
        mock_session_class.return_value = mock_session
        
        report = check_health()
        
        assert report.aws_cli is False
        assert report.session_manager_plugin is True
        assert report.aws_credentials is True
    
    @patch('src.health.shutil.which')
    @patch('src.health.boto3.session.Session')
    def test_check_health_missing_plugin(self, mock_session_class, mock_which):
        """Test health check when Session Manager Plugin is missing"""
        mock_which.side_effect = lambda cmd: "/usr/bin/aws" if cmd == "aws" else None
        
        mock_session = MagicMock()
        mock_session.get_credentials.return_value = MagicMock()
        mock_session_class.return_value = mock_session
        
        report = check_health()
        
        assert report.aws_cli is True
        assert report.session_manager_plugin is False
        assert report.aws_credentials is True
    
    @patch('src.health.shutil.which')
    @patch('src.health.boto3.session.Session')
    def test_check_health_no_credentials(self, mock_session_class, mock_which):
        """Test health check when AWS credentials are missing"""
        mock_which.side_effect = lambda cmd: "/usr/bin/aws" if cmd == "aws" else "/usr/bin/session-manager-plugin"
        
        mock_session = MagicMock()
        mock_session.get_credentials.return_value = None
        mock_session_class.return_value = mock_session
        
        report = check_health()
        
        assert report.aws_cli is True
        assert report.session_manager_plugin is True
        assert report.aws_credentials is False
    
    @patch('src.health.shutil.which')
    @patch('src.health.boto3.session.Session')
    def test_check_health_credentials_exception(self, mock_session_class, mock_which):
        """Test health check when getting credentials raises an exception"""
        mock_which.side_effect = lambda cmd: "/usr/bin/aws" if cmd == "aws" else "/usr/bin/session-manager-plugin"
        
        mock_session = MagicMock()
        mock_session.get_credentials.side_effect = Exception("Credential error")
        mock_session_class.return_value = mock_session
        
        report = check_health()
        
        assert report.aws_cli is True
        assert report.session_manager_plugin is True
        assert report.aws_credentials is False
    
    @patch('src.health.shutil.which')
    @patch('src.health.boto3.session.Session')
    def test_check_health_all_missing(self, mock_session_class, mock_which):
        """Test health check when all dependencies are missing"""
        mock_which.return_value = None
        
        mock_session = MagicMock()
        mock_session.get_credentials.return_value = None
        mock_session_class.return_value = mock_session
        
        report = check_health()
        
        assert report.aws_cli is False
        assert report.session_manager_plugin is False
        assert report.aws_credentials is False
