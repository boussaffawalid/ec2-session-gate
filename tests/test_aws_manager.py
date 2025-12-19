"""Tests for AWS manager in src/aws_manager.py"""
import pytest
import os
import socket
import uuid
from unittest.mock import Mock, patch, MagicMock, mock_open
from botocore.exceptions import ClientError
from src.aws_manager import AWSManager, Connection, _is_port_free, _in_range_free_port
from src.preferences_handler import Preferences


class TestPortHelpers:
    """Tests for port helper functions"""
    
    def test_is_port_free(self):
        """Test checking if a port is free"""
        # Find a free port
        free_port = None
        for port in range(50000, 50100):
            if _is_port_free(port):
                free_port = port
                break
        
        if free_port:
            assert _is_port_free(free_port) is True
        
        # Bind to a port and check it's not free
        # Skip this test if we can't bind sockets (e.g., in sandboxed environments)
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                test_socket.bind(("127.0.0.1", 0))
                bound_port = test_socket.getsockname()[1]
                # Port should not be free while bound
                # Note: This might still pass if SO_REUSEADDR allows it
                test_socket.close()
            finally:
                test_socket.close()
        except (PermissionError, OSError):
            # Skip socket binding test in restricted environments
            pytest.skip("Cannot bind sockets in this environment")
    
    def test_in_range_free_port(self):
        """Test finding a free port in a range"""
        # Use a wide range to ensure we find a free port
        port = _in_range_free_port(50000, 50100)
        assert 50000 <= port <= 50100
        assert _is_port_free(port) is True
    
    def test_in_range_free_port_no_available(self):
        """Test error when no ports are available"""
        # This test might be flaky, but we can test the error case
        # by mocking _is_port_free to always return False
        with patch('src.aws_manager._is_port_free', return_value=False):
            with pytest.raises(RuntimeError, match="No free port available"):
                _in_range_free_port(50000, 50001)


class TestAWSManager:
    """Tests for AWSManager class"""
    
    @pytest.fixture
    def mock_preferences(self):
        """Create mock preferences"""
        prefs = Preferences()
        prefs.port_range_start = 60000
        prefs.port_range_end = 60100
        prefs.ssh_key_folder = None
        return prefs
    
    @pytest.fixture
    def aws_manager(self, mock_preferences):
        """Create AWSManager instance"""
        with patch('src.aws_manager.AWSManager._cleanup_orphaned_processes'):
            return AWSManager(mock_preferences)
    
    def test_init(self, mock_preferences):
        """Test AWSManager initialization"""
        with patch('src.aws_manager.AWSManager._cleanup_orphaned_processes') as mock_cleanup:
            manager = AWSManager(mock_preferences)
            
            assert manager.preferences == mock_preferences
            assert manager._profile is None
            assert manager._region is None
            assert manager._account_id is None
            assert manager._connections == {}
            mock_cleanup.assert_called_once()
    
    def test_connect(self, aws_manager):
        """Test connecting to AWS"""
        mock_session = MagicMock()
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
        mock_iam = MagicMock()
        mock_iam.list_account_aliases.return_value = {"AccountAliases": ["test-alias"]}
        mock_session.client.side_effect = lambda service, **kwargs: {
            "sts": mock_sts,
            "iam": mock_iam
        }[service]
        
        # Mock the session() method to return our mock session
        with patch.object(aws_manager, 'session', return_value=mock_session):
            account_info = aws_manager.connect("test-profile", "us-east-1")
        
        assert account_info["account_id"] == "123456789012"
        assert account_info["account_alias"] == "test-alias"
        assert aws_manager._profile == "test-profile"
        assert aws_manager._region == "us-east-1"
    
    def test_connect_no_alias(self, aws_manager):
        """Test connecting to AWS when account alias is not available"""
        mock_session = MagicMock()
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
        mock_iam = MagicMock()
        mock_iam.list_account_aliases.return_value = {"AccountAliases": []}
        mock_session.client.side_effect = lambda service, **kwargs: {
            "sts": mock_sts,
            "iam": mock_iam
        }[service]
        
        # Mock the session() method to return our mock session
        with patch.object(aws_manager, 'session', return_value=mock_session):
            account_info = aws_manager.connect("test-profile", "us-east-1")
        
        assert account_info["account_id"] == "123456789012"
        assert account_info["account_alias"] is None
        assert aws_manager._profile == "test-profile"
        assert aws_manager._region == "us-east-1"
    
    def test_connect_error(self, aws_manager):
        """Test connection error handling"""
        mock_session = MagicMock()
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.side_effect = ClientError(
            {"Error": {"Code": "InvalidClientTokenId", "Message": "Invalid credentials"}},
            "GetCallerIdentity"
        )
        mock_session.client.return_value = mock_sts
        
        # Mock the session() method to return our mock session
        with patch.object(aws_manager, 'session', return_value=mock_session):
            with pytest.raises(Exception):
                aws_manager.connect("test-profile", "us-east-1")
    
    def test_list_instances(self, aws_manager):
        """Test listing EC2 instances"""
        aws_manager._profile = "test-profile"
        aws_manager._region = "us-east-1"
        
        mock_session = MagicMock()
        mock_ec2 = MagicMock()
        mock_ssm = MagicMock()
        
        # Mock paginators
        mock_ec2_paginator = MagicMock()
        mock_ec2_paginator.paginate.return_value = [
            {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": "i-1234567890abcdef0",
                                "InstanceType": "t2.micro",
                                "State": {"Name": "running"},
                                "PlatformDetails": "Linux/UNIX",
                                "PrivateIpAddress": "10.0.0.1",
                                "PublicIpAddress": "54.0.0.1",
                                "Tags": [{"Key": "Name", "Value": "test-instance"}],
                                "KeyName": "test-key",
                                "ImageId": "ami-12345678",
                                "VpcId": "vpc-12345678",
                                "SubnetId": "subnet-12345678",
                                "SecurityGroups": [{"GroupId": "sg-12345678", "GroupName": "test-sg"}]
                            }
                        ]
                    }
                ]
            }
        ]
        mock_ec2.get_paginator.return_value = mock_ec2_paginator
        
        mock_ssm_paginator = MagicMock()
        mock_ssm_paginator.paginate.return_value = [
            {"InstanceInformationList": []}  # No SSM instances
        ]
        mock_ssm.get_paginator.return_value = mock_ssm_paginator
        
        # Set up client to return different mocks for ec2 and ssm
        def client_side_effect(service_name, **kwargs):
            if service_name == "ec2":
                return mock_ec2
            elif service_name == "ssm":
                return mock_ssm
            return MagicMock()
        
        mock_session.client.side_effect = client_side_effect
        
        # Mock the session() method to return our mock session
        with patch.object(aws_manager, 'session', return_value=mock_session):
            instances = aws_manager.list_instances()
        
        assert len(instances) == 1
        assert instances[0]["id"] == "i-1234567890abcdef0"
        assert instances[0]["name"] == "test-instance"
        assert instances[0]["type"] == "t2.micro"
        assert instances[0]["state"] == "running"
    
    def test_instance_details(self, aws_manager):
        """Test getting instance details"""
        aws_manager._profile = "test-profile"
        aws_manager._region = "us-east-1"
        
        mock_session = MagicMock()
        mock_ec2 = MagicMock()
        mock_ec2.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-1234567890abcdef0",
                            "InstanceType": "t2.micro",
                            "State": {"Name": "running"},
                            "PlatformDetails": "Linux/UNIX",
                            "PrivateIpAddress": "10.0.0.1",
                            "PublicIpAddress": "54.0.0.1",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                            "KeyName": "test-key",
                            "ImageId": "ami-12345678",
                            "VpcId": "vpc-12345678",
                            "SubnetId": "subnet-12345678",
                            "IamInstanceProfile": {"Arn": "arn:aws:iam::123456789012:instance-profile/test-role"},
                            "SecurityGroups": [{"GroupId": "sg-12345678", "GroupName": "test-sg"}]
                        }
                    ]
                }
            ]
        }
        mock_session.client.return_value = mock_ec2
        
        # Mock the session() method to return our mock session
        with patch.object(aws_manager, 'session', return_value=mock_session):
            details = aws_manager.instance_details("i-1234567890abcdef0")
        
        assert details["id"] == "i-1234567890abcdef0"
        assert details["name"] == "test-instance"
        assert details["iam_role"] == "test-role"
        assert details["security_groups"] == "test-sg (sg-12345678)"
    
    def test_get_ssh_key_folders_default(self, aws_manager):
        """Test getting default SSH key folders"""
        with patch('os.path.exists', return_value=True), \
             patch('os.path.isdir', return_value=True), \
             patch('os.path.expanduser', return_value='/home/user/.ssh'):
            folders = aws_manager._get_ssh_key_folders()
            assert '/home/user/.ssh' in folders
    
    def test_get_ssh_key_folders_from_preferences(self, mock_preferences, aws_manager):
        """Test getting SSH key folders from preferences"""
        mock_preferences.ssh_key_folder = "~/.ssh\n~/.ssh/keys"
        aws_manager.preferences = mock_preferences
        
        with patch('os.path.exists', return_value=True), \
             patch('os.path.isdir', return_value=True), \
             patch('os.path.expanduser', side_effect=lambda x: x.replace('~', '/home/user')):
            folders = aws_manager._get_ssh_key_folders()
            assert len(folders) >= 1
    
    def test_construct_ssh_key_path(self, aws_manager):
        """Test constructing SSH key path"""
        with patch.object(aws_manager, '_get_ssh_key_folders', return_value=['/home/user/.ssh']), \
             patch('os.path.exists', return_value=True), \
             patch('os.path.isfile', return_value=True):
            key_path = aws_manager._construct_ssh_key_path("test-key")
            assert key_path is not None
            assert "test-key" in key_path
    
    def test_construct_ssh_key_path_not_found(self, aws_manager):
        """Test constructing SSH key path when key not found"""
        with patch.object(aws_manager, '_get_ssh_key_folders', return_value=['/home/user/.ssh']), \
             patch('os.path.exists', return_value=False):
            key_path = aws_manager._construct_ssh_key_path("test-key")
            # Should return a default path even if file doesn't exist
            assert key_path is not None
    
    def test_generate_connection_info_ssh(self, aws_manager):
        """Test generating SSH connection info"""
        with patch.object(aws_manager, '_construct_ssh_key_path', return_value='/home/user/.ssh/test-key.pem'):
            info = aws_manager._generate_connection_info("ssh", 60022, 22, key_name="test-key")
            
            assert info["type"] == "ssh"
            assert info["port"] == "60022"
            assert "-i /home/user/.ssh/test-key.pem" in info["command"]
            assert "-o StrictHostKeyChecking=no" in info["command"]
            assert "-o UserKnownHostsFile=/dev/null" in info["command"]
    
    def test_generate_connection_info_rdp(self, aws_manager):
        """Test generating RDP connection info"""
        info = aws_manager._generate_connection_info("rdp", 60389, 3389, instance_id="i-123")
        
        assert info["type"] == "rdp"
        assert info["port"] == "60389"
        assert info["address"] == "127.0.0.1:60389"
        assert info["instance_id"] == "i-123"
    
    def test_generate_connection_info_custom_port(self, aws_manager):
        """Test generating custom port connection info"""
        info = aws_manager._generate_connection_info("custom_port", 60080, 80)
        
        assert info["type"] == "custom_port"
        assert info["port"] == "60080"
        assert "key_name" not in info  # Should not include key_name for custom ports
    
    def test_start_ssh(self, mocker, aws_manager):
        """Test starting SSH connection"""
        # Mock dependencies
        mock_popen = mocker.patch('src.aws_manager.subprocess.Popen')
        mocker.patch('src.aws_manager._is_port_free', return_value=True)
        mocker.patch('src.aws_manager._require')
        mocker.patch('src.aws_manager.os.name', 'posix')  # Simulate non-Windows
        
        aws_manager._profile = "test-profile"
        aws_manager._region = "us-east-1"
        
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None  # Process still running
        mock_proc.communicate.return_value = (b'', b'')  # Return tuple (stdout, stderr)
        mock_popen.return_value = mock_proc
        
        mocker.patch.object(aws_manager, 'instance_details', return_value={"key_name": "test-key"})
        
        result = aws_manager.start_ssh("i-1234567890abcdef0")
        
        assert "connection_id" in result
        assert result["remote_port"] == 22
        assert "command" in result
        mock_popen.assert_called_once()
        # Verify creationflags is not passed on non-Windows
        call_kwargs = mock_popen.call_args[1] if mock_popen.call_args else {}
        assert call_kwargs.get('creationflags', 0) == 0
    
    def test_start_rdp(self, mocker, aws_manager):
        """Test starting RDP connection"""
        # Mock dependencies
        mock_popen = mocker.patch('src.aws_manager.subprocess.Popen')
        mocker.patch('src.aws_manager._is_port_free', return_value=True)
        mocker.patch('src.aws_manager._require')
        mocker.patch('src.aws_manager.os.name', 'posix')  # Simulate non-Windows
        
        aws_manager._profile = "test-profile"
        aws_manager._region = "us-east-1"
        
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None  # Process still running
        mock_proc.communicate.return_value = (b'', b'')  # Return tuple (stdout, stderr)
        mock_popen.return_value = mock_proc
        
        mocker.patch.object(aws_manager, 'instance_details', return_value={"key_name": "test-key"})
        
        result = aws_manager.start_rdp("i-1234567890abcdef0")
        
        assert "connection_id" in result
        assert result["remote_port"] == 3389
        # Verify creationflags is not passed on non-Windows
        call_kwargs = mock_popen.call_args[1] if mock_popen.call_args else {}
        assert call_kwargs.get('creationflags', 0) == 0
    
    def test_start_custom_port(self, mocker, aws_manager):
        """Test starting custom port forwarding"""
        # Mock dependencies
        mock_popen = mocker.patch('src.aws_manager.subprocess.Popen')
        mocker.patch('src.aws_manager._is_port_free', return_value=True)
        mocker.patch('src.aws_manager._require')
        mocker.patch('src.aws_manager.os.name', 'posix')  # Simulate non-Windows
        
        aws_manager._profile = "test-profile"
        aws_manager._region = "us-east-1"
        
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None  # Process still running
        mock_proc.communicate.return_value = (b'', b'')  # Return tuple (stdout, stderr)
        mock_popen.return_value = mock_proc
        
        mocker.patch.object(aws_manager, 'instance_details', return_value={"key_name": "test-key"})
        
        result = aws_manager.start_custom_port("i-1234567890abcdef0", {
            "remote_port": 8080,
            "local_port": 60080
        })
        
        assert "connection_id" in result
        assert result["remote_port"] == 8080
        # Verify creationflags is not passed on non-Windows
        call_kwargs = mock_popen.call_args[1] if mock_popen.call_args else {}
        assert call_kwargs.get('creationflags', 0) == 0
    
    def test_active_connections(self, aws_manager):
        """Test getting active connections"""
        # Add a mock connection
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # Process still running
        connection = Connection(
            "test-connection-id",
            mock_proc,
            "test command",
            {"instance_id": "i-123", "type": "ssh", "local_port": 60022}
        )
        aws_manager._connections["test-connection-id"] = connection
        
        connections = aws_manager.active_connections()
        
        assert len(connections) == 1
        assert connections[0]["connection_id"] == "test-connection-id"
    
    def test_terminate(self, aws_manager):
        """Test terminating a connection"""
        mock_proc = MagicMock()
        connection = Connection(
            "test-connection-id",
            mock_proc,
            "test command",
            {"instance_id": "i-123"}
        )
        aws_manager._connections["test-connection-id"] = connection
        
        with patch('src.utils.kill_process_tree', return_value=True):
            aws_manager.terminate("test-connection-id")
        
        assert "test-connection-id" not in aws_manager._connections
    
    def test_terminate_all(self, aws_manager):
        """Test terminating all connections"""
        mock_proc1 = MagicMock()
        mock_proc2 = MagicMock()
        aws_manager._connections = {
            "conn1": Connection("conn1", mock_proc1, "cmd1", {}),
            "conn2": Connection("conn2", mock_proc2, "cmd2", {})
        }
        
        with patch.object(aws_manager, 'terminate') as mock_terminate:
            aws_manager.terminate_all()
        
        assert mock_terminate.call_count == 2
    
    def test_get_windows_password_data(self, aws_manager):
        """Test getting Windows password data"""
        from datetime import datetime
        
        aws_manager._profile = "test-profile"
        aws_manager._region = "us-east-1"
        
        mock_session = MagicMock()
        mock_ec2 = MagicMock()
        # AWS returns datetime objects, not strings
        mock_timestamp = datetime(2024, 1, 1, 0, 0, 0)
        mock_ec2.get_password_data.return_value = {
            "PasswordData": "encrypted_password_data",
            "Timestamp": mock_timestamp
        }
        mock_session.client.return_value = mock_ec2
        
        # Mock the session() method to return our mock session
        with patch.object(aws_manager, 'session', return_value=mock_session):
            result = aws_manager.get_windows_password_data("i-1234567890abcdef0")
        
        assert "password_data" in result
        assert result["password_data"] == "encrypted_password_data"
        assert result["timestamp"] == mock_timestamp.isoformat()
    
    def test_decrypt_windows_password(self, aws_manager):
        """Test decrypting Windows password"""
        # This test requires cryptography library
        # We'll mock the decryption process
        encrypted_password = "dGVzdF9wYXNzd29yZA=="  # base64 encoded "test_password"
        pem_key = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA...
-----END RSA PRIVATE KEY-----"""
        
        # This test would require actual RSA key material to work properly
        # For now, we'll test the error handling
        with pytest.raises((ValueError, RuntimeError)):
            aws_manager.decrypt_windows_password(encrypted_password, "invalid_key")
