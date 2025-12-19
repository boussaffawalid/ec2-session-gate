"""Tests for API endpoints in src/api.py"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from flask import Flask
from src.app import create_app
from src.preferences_handler import Preferences


@pytest.fixture
def app():
    """Create Flask app for testing"""
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture
def mock_aws_manager():
    """Create mock AWS manager"""
    # Patch the aws_manager instance in the api module
    with patch('src.api.aws_manager') as mock_manager:
        # Set up default return values
        mock_manager.list_profiles.return_value = []
        mock_manager.list_instances.return_value = []
        mock_manager.active_connections.return_value = []
        yield mock_manager


class TestProfilesEndpoint:
    """Tests for /api/profiles endpoint"""
    
    def test_get_profiles_success(self, client, mock_aws_manager):
        """Test getting AWS profiles"""
        mock_aws_manager.list_profiles.return_value = ["default", "test-profile"]
        
        response = client.get('/api/profiles')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == ["default", "test-profile"]
    
    def test_get_profiles_error(self, client, mock_aws_manager):
        """Test error handling in get_profiles"""
        mock_aws_manager.list_profiles.side_effect = Exception("AWS error")
        
        response = client.get('/api/profiles')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert data["status"] == "error"


class TestRegionsEndpoint:
    """Tests for /api/regions endpoint"""
    
    def test_get_regions_success(self, client, mock_aws_manager):
        """Test getting AWS regions"""
        mock_session = MagicMock()
        mock_ec2 = MagicMock()
        mock_ec2.describe_regions.return_value = {
            "Regions": [
                {"RegionName": "us-east-1"},
                {"RegionName": "us-west-2"}
            ]
        }
        mock_session.client.return_value = mock_ec2
        mock_aws_manager.session.return_value = mock_session
        
        response = client.get('/api/regions?profile=default')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["ok"] is True
        assert "us-east-1" in data["data"]
        assert "us-west-2" in data["data"]
    
    def test_get_regions_error(self, client, mock_aws_manager):
        """Test error handling in get_regions"""
        mock_aws_manager.session.side_effect = Exception("AWS error")
        
        response = client.get('/api/regions?profile=default')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert data["ok"] is False


class TestConnectEndpoint:
    """Tests for /api/connect endpoint"""
    
    def test_connect_success(self, client, mock_aws_manager):
        """Test successful AWS connection"""
        mock_aws_manager.connect.return_value = {
            "account_id": "123456789012",
            "account_alias": "test-alias"
        }
        
        response = client.post('/api/connect', 
                              json={"profile": "test-profile", "region": "us-east-1"})
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert data["account_id"] == "123456789012"
        assert data["account_alias"] == "test-alias"
        mock_aws_manager.connect.assert_called_once_with("test-profile", "us-east-1")
    
    def test_connect_success_no_alias(self, client, mock_aws_manager):
        """Test successful AWS connection without account alias"""
        mock_aws_manager.connect.return_value = {
            "account_id": "123456789012",
            "account_alias": None
        }
        
        response = client.post('/api/connect', 
                              json={"profile": "test-profile", "region": "us-east-1"})
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert data["account_id"] == "123456789012"
        assert data.get("account_alias") is None
        mock_aws_manager.connect.assert_called_once_with("test-profile", "us-east-1")
    
    def test_connect_missing_params(self, client):
        """Test connect with missing parameters"""
        response = client.post('/api/connect', json={})
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["status"] == "error"
    
    def test_connect_aws_error(self, client, mock_aws_manager):
        """Test connect with AWS error"""
        from botocore.exceptions import ClientError
        error = ClientError(
            {"Error": {"Code": "AuthFailure", "Message": "Invalid credentials"}},
            "GetCallerIdentity"
        )
        mock_aws_manager.connect.side_effect = error
        
        response = client.post('/api/connect',
                              json={"profile": "test-profile", "region": "us-east-1"})
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["status"] == "error"


class TestInstancesEndpoint:
    """Tests for /api/instances endpoint"""
    
    def test_get_instances_success(self, client, mock_aws_manager):
        """Test getting instances"""
        mock_aws_manager.list_instances.return_value = [
            {"id": "i-123", "name": "test-instance", "state": "running"}
        ]
        
        response = client.get('/api/instances')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 1
        assert data[0]["id"] == "i-123"
    
    def test_get_instances_error(self, client, mock_aws_manager):
        """Test error handling in get_instances"""
        mock_aws_manager.list_instances.side_effect = Exception("AWS error")
        
        response = client.get('/api/instances')
        
        assert response.status_code == 500


class TestSSHEndpoint:
    """Tests for /api/ssh/<instance_id> endpoint"""
    
    def test_start_ssh_success(self, client, mock_aws_manager):
        """Test starting SSH connection"""
        mock_aws_manager.start_ssh.return_value = {
            "connection_id": "conn-123",
            "local_port": 60022,
            "command": "ssh ..."
        }
        
        response = client.post('/api/ssh/i-1234567890abcdef0', json={})
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert data["connection_id"] == "conn-123"
    
    def test_start_ssh_error(self, client, mock_aws_manager):
        """Test error handling in start_ssh"""
        mock_aws_manager.start_ssh.side_effect = Exception("Connection error")
        
        response = client.post('/api/ssh/i-1234567890abcdef0', json={})
        
        assert response.status_code == 400


class TestRDPEndpoint:
    """Tests for /api/rdp/<instance_id> endpoint"""
    
    def test_start_rdp_success(self, client, mock_aws_manager):
        """Test starting RDP connection"""
        mock_aws_manager.start_rdp.return_value = {
            "connection_id": "conn-123",
            "local_port": 60389,
            "address": "127.0.0.1:60389"
        }
        
        response = client.post('/api/rdp/i-1234567890abcdef0', json={})
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
    
    def test_start_rdp_error(self, client, mock_aws_manager):
        """Test error handling in start_rdp"""
        mock_aws_manager.start_rdp.side_effect = Exception("Connection error")
        
        response = client.post('/api/rdp/i-1234567890abcdef0', json={})
        
        assert response.status_code == 400


class TestCustomPortEndpoint:
    """Tests for /api/custom-port/<instance_id> endpoint"""
    
    def test_start_custom_port_success(self, client, mock_aws_manager):
        """Test starting custom port forwarding"""
        mock_aws_manager.start_custom_port.return_value = {
            "connection_id": "conn-123",
            "local_port": 60080,
            "remote_port": 8080
        }
        
        response = client.post('/api/custom-port/i-1234567890abcdef0',
                              json={"remote_port": 8080, "local_port": 60080})
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
    
    def test_start_custom_port_error(self, client, mock_aws_manager):
        """Test error handling in start_custom_port"""
        mock_aws_manager.start_custom_port.side_effect = Exception("Connection error")
        
        response = client.post('/api/custom-port/i-1234567890abcdef0',
                              json={"remote_port": 8080})
        
        assert response.status_code == 400


class TestTerminateEndpoint:
    """Tests for /api/terminate-connection/<connection_id> endpoint"""
    
    def test_terminate_success(self, client, mock_aws_manager):
        """Test terminating a connection"""
        mock_aws_manager.terminate.return_value = None
        connection_id = "12345678-1234-1234-1234-123456789012"
        
        response = client.post(f'/api/terminate-connection/{connection_id}')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        mock_aws_manager.terminate.assert_called_once_with(connection_id)
    
    def test_terminate_error(self, client, mock_aws_manager):
        """Test error handling in terminate"""
        mock_aws_manager.terminate.side_effect = Exception("Termination error")
        connection_id = "12345678-1234-1234-1234-123456789012"
        
        response = client.post(f'/api/terminate-connection/{connection_id}')
        
        assert response.status_code == 400


class TestTerminateAllEndpoint:
    """Tests for /api/terminate-all-connections endpoint"""
    
    def test_terminate_all_success(self, client, mock_aws_manager):
        """Test terminating all connections"""
        mock_aws_manager.terminate_all.return_value = None
        
        response = client.post('/api/terminate-all-connections')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        mock_aws_manager.terminate_all.assert_called_once()


class TestActiveConnectionsEndpoint:
    """Tests for /api/active-connections endpoint"""
    
    def test_get_active_connections_success(self, client, mock_aws_manager):
        """Test getting active connections"""
        mock_aws_manager.active_connections.return_value = [
            {"connection_id": "conn-1", "type": "ssh"},
            {"connection_id": "conn-2", "type": "rdp"}
        ]
        
        response = client.get('/api/active-connections')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 2


class TestPreferencesEndpoint:
    """Tests for /api/preferences endpoints"""
    
    def test_get_preferences(self, client):
        """Test getting preferences"""
        with patch('src.api.Preferences.load') as mock_load:
            mock_prefs = Mock()
            mock_prefs.to_dict.return_value = {
                "port_range": {"start": 60000, "end": 60100},
                "logging": {"level": "INFO"}
            }
            mock_load.return_value = mock_prefs
            
            response = client.get('/api/preferences')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert "port_range" in data
    
    def test_set_preferences(self, client):
        """Test setting preferences"""
        with patch('src.api.Preferences.load') as mock_load, \
             patch('src.api.Preferences.from_dict') as mock_from_dict, \
             patch('src.api.aws_manager') as mock_manager:
            
            mock_prefs = Mock()
            mock_prefs.to_dict.return_value = {"port_range": {"start": 60000, "end": 60100}}
            mock_prefs.save = Mock()
            mock_prefs.port_range_start = 60000
            mock_prefs.port_range_end = 60100
            mock_from_dict.return_value = mock_prefs
            mock_load.return_value = mock_prefs
            
            response = client.post('/api/preferences',
                                  json={"port_range": {"start": 60000, "end": 60100}})
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["status"] == "success"
            mock_prefs.save.assert_called_once()


class TestHealthEndpoint:
    """Tests for /api/health endpoint"""
    
    def test_get_health(self, client):
        """Test health check endpoint"""
        with patch('src.api.check_health') as mock_check:
            mock_health = Mock()
            mock_health.to_dict.return_value = {
                "aws_cli": True,
                "session_manager_plugin": True,
                "aws_credentials": True,
                "os": "Linux"
            }
            mock_check.return_value = mock_health
            
            response = client.get('/api/health')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["aws_cli"] is True


class TestVersionEndpoint:
    """Tests for /api/version endpoint"""
    
    def test_get_version(self, client):
        """Test version endpoint"""
        response = client.get('/api/version')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "version" in data


class TestWindowsPasswordEndpoint:
    """Tests for /api/windows-password/<instance_id> endpoint"""
    
    def test_get_windows_password_success(self, client, mock_aws_manager):
        """Test getting Windows password"""
        mock_aws_manager.get_windows_password_data.return_value = {
            "password_data": "encrypted_data",
            "timestamp": "2024-01-01T00:00:00Z"
        }
        mock_aws_manager.decrypt_windows_password.return_value = "decrypted_password"
        instance_id = "i-1234567890abcdef0"
        
        response = client.post(f'/api/windows-password/{instance_id}',
                               json={"pem_key": "key_content", "key_name": "test-key"})
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert data["password"] == "decrypted_password"
    
    def test_get_windows_password_no_key(self, client):
        """Test getting Windows password without key"""
        instance_id = "i-1234567890abcdef0"
        response = client.post(f'/api/windows-password/{instance_id}', json={})
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["status"] == "error"
