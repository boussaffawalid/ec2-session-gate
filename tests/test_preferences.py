"""Tests for preferences handler in src/preferences_handler.py"""
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
from src.preferences_handler import Preferences, DEFAULTS, PREF_PATH


class TestPreferences:
    """Tests for Preferences class"""
    
    def test_default_preferences(self):
        """Test creating preferences with defaults"""
        prefs = Preferences()
        
        assert prefs.port_range_start == DEFAULTS["port_range"]["start"]
        assert prefs.port_range_end == DEFAULTS["port_range"]["end"]
        assert prefs.logging_level == DEFAULTS["logging"]["level"]
        assert prefs.logging_format == DEFAULTS["logging"]["format"]
        assert prefs.last_profile is None
        assert prefs.last_region is None
        assert prefs.ssh_key_folder is None
    
    def test_from_dict(self):
        """Test creating preferences from dictionary"""
        data = {
            "port_range": {"start": 50000, "end": 50100},
            "logging": {"level": "DEBUG", "format": "custom"},
            "aws": {"profile": "test-profile", "region": "us-west-2"},
            "ssh_key_folder": "~/.ssh"
        }
        
        prefs = Preferences.from_dict(data)
        
        assert prefs.port_range_start == 50000
        assert prefs.port_range_end == 50100
        assert prefs.logging_level == "DEBUG"
        assert prefs.logging_format == "custom"
        assert prefs.last_profile == "test-profile"
        assert prefs.last_region == "us-west-2"
        assert prefs.ssh_key_folder == "~/.ssh"
    
    def test_from_dict_partial(self):
        """Test creating preferences from partial dictionary"""
        data = {
            "port_range": {"start": 50000}
        }
        
        prefs = Preferences.from_dict(data)
        
        assert prefs.port_range_start == 50000
        assert prefs.port_range_end == DEFAULTS["port_range"]["end"]
        assert prefs.last_profile is None
    
    def test_to_dict(self):
        """Test converting preferences to dictionary"""
        prefs = Preferences(
            port_range_start=50000,
            port_range_end=50100,
            logging_level="DEBUG",
            last_profile="test-profile",
            last_region="us-west-2",
            ssh_key_folder="~/.ssh"
        )
        
        result = prefs.to_dict()
        
        assert result["port_range"]["start"] == 50000
        assert result["port_range"]["end"] == 50100
        assert result["logging"]["level"] == "DEBUG"
        assert result["aws"]["profile"] == "test-profile"
        assert result["aws"]["region"] == "us-west-2"
        assert result["ssh_key_folder"] == "~/.ssh"
    
    def test_to_dict_no_aws(self):
        """Test to_dict without AWS settings"""
        prefs = Preferences()
        
        result = prefs.to_dict()
        
        assert "aws" not in result
        assert "ssh_key_folder" not in result
    
    def test_to_dict_partial_aws(self):
        """Test to_dict with partial AWS settings"""
        prefs = Preferences(last_profile="test-profile")
        
        result = prefs.to_dict()
        
        assert result["aws"]["profile"] == "test-profile"
        assert "region" not in result["aws"]
    
    def test_load_existing(self):
        """Test loading existing preferences"""
        mock_data = {
            "port_range": {"start": 50000, "end": 50100},
            "logging": {"level": "DEBUG"},
            "aws": {"profile": "test-profile"}
        }
        
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = json.dumps(mock_data)
        
        with patch('src.preferences_handler.PREF_PATH', mock_path):
            prefs = Preferences.load()
        
        assert prefs.port_range_start == 50000
        assert prefs.port_range_end == 50100
        assert prefs.logging_level == "DEBUG"
        assert prefs.last_profile == "test-profile"
    
    def test_load_nonexistent(self):
        """Test loading preferences when file doesn't exist"""
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        
        with patch('src.preferences_handler.PREF_PATH', mock_path):
            prefs = Preferences.load()
        
        assert prefs.port_range_start == DEFAULTS["port_range"]["start"]
        assert prefs.port_range_end == DEFAULTS["port_range"]["end"]
    
    def test_load_invalid_json(self):
        """Test loading preferences with invalid JSON"""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.read_text.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        
        with patch('src.preferences_handler.PREF_PATH', mock_path):
            prefs = Preferences.load()
        
        # Should return defaults on error
        assert prefs.port_range_start == DEFAULTS["port_range"]["start"]
    
    def test_save(self):
        """Test saving preferences"""
        prefs = Preferences(
            port_range_start=50000,
            port_range_end=50100,
            logging_level="DEBUG",
            last_profile="test-profile"
        )
        
        mock_path = MagicMock()
        mock_path.parent.mkdir = MagicMock()
        mock_path.write_text = MagicMock()
        
        with patch('src.preferences_handler.PREF_PATH', mock_path):
            prefs.save()
        
        # Verify mkdir and write_text were called
        mock_path.parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_path.write_text.assert_called_once()
        
        # Get the written content
        written_content = mock_path.write_text.call_args[0][0]
        written_data = json.loads(written_content)
        assert written_data["port_range"]["start"] == 50000
        assert written_data["aws"]["profile"] == "test-profile"
