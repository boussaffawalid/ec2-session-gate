"""Shared pytest fixtures and configuration"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from src.preferences_handler import Preferences


@pytest.fixture
def mock_preferences():
    """Create mock preferences for testing"""
    prefs = Preferences()
    prefs.port_range_start = 60000
    prefs.port_range_end = 60100
    prefs.ssh_key_folder = None
    prefs.last_profile = None
    prefs.last_region = None
    return prefs


@pytest.fixture
def mock_aws_manager():
    """Create a mock AWS manager"""
    manager = MagicMock()
    manager._connections = {}
    manager._profile = None
    manager._region = None
    manager._account_id = None
    return manager
