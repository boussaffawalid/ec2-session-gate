"""Tests for utility functions in src/utils.py"""
import pytest
import subprocess
from unittest.mock import Mock, patch, MagicMock
from src.utils import (
    kill_process_tree,
    check_aws_dependencies,
    validate_remote_host,
    validate_port,
    which,
    require_cmd
)


class TestKillProcessTree:
    """Tests for kill_process_tree function"""
    
    @patch('src.utils.psutil.Process')
    def test_kill_process_tree_success(self, mock_process_class):
        """Test successful process tree termination"""
        # Mock parent process
        mock_parent = Mock()
        mock_parent.pid = 12345
        
        # Mock children
        mock_child1 = Mock()
        mock_child1.is_running.return_value = False
        mock_child2 = Mock()
        mock_child2.is_running.return_value = True
        
        mock_parent.children.return_value = [mock_child1, mock_child2]
        mock_process_class.return_value = mock_parent
        
        # Mock wait to succeed
        mock_parent.wait.return_value = None
        mock_child1.wait.return_value = None
        mock_child2.wait.return_value = None
        
        result = kill_process_tree(12345)
        
        assert result is True
        mock_parent.terminate.assert_called_once()
        mock_child1.terminate.assert_called_once()
        mock_child2.terminate.assert_called_once()
    
    @patch('src.utils.psutil.Process')
    def test_kill_process_tree_timeout(self, mock_process_class):
        """Test process tree termination with timeout"""
        import psutil
        
        mock_parent = Mock()
        mock_parent.pid = 12345
        mock_parent.children.return_value = []
        mock_process_class.return_value = mock_parent
        
        # Simulate timeout
        mock_parent.wait.side_effect = psutil.TimeoutExpired("wait", 5)
        
        result = kill_process_tree(12345)
        
        assert result is True
        mock_parent.terminate.assert_called_once()
        mock_parent.kill.assert_called_once()
    
    @patch('src.utils.psutil.Process')
    def test_kill_process_tree_no_such_process(self, mock_process_class):
        """Test handling of non-existent process"""
        import psutil
        
        mock_process_class.side_effect = psutil.NoSuchProcess(12345)
        
        result = kill_process_tree(12345)
        
        assert result is False


class TestCheckAwsDependencies:
    """Tests for check_aws_dependencies function"""
    
    def test_check_aws_dependencies_success_non_windows(self, mocker):
        """Test successful AWS dependencies check on non-Windows"""
        mock_check_output = mocker.patch('src.utils.subprocess.check_output')
        mocker.patch('src.utils.os.name', 'posix')  # Simulate non-Windows
        
        mock_check_output.return_value = b"aws-cli/2.0.0"
        
        result = check_aws_dependencies()
        
        assert result is True
        assert mock_check_output.call_count == 2
        # Verify no creationflags passed on non-Windows
        for call in mock_check_output.call_args_list:
            assert 'creationflags' not in call.kwargs or call.kwargs.get('creationflags') == 0
    
    def test_check_aws_dependencies_success_windows(self, mocker):
        """Test successful AWS dependencies check on Windows"""
        mock_check_output = mocker.patch('src.utils.subprocess.check_output')
        mocker.patch('src.utils.os.name', 'nt')  # Simulate Windows
        
        # Mock subprocess.CREATE_NO_WINDOW since it doesn't exist on non-Windows
        # We need to patch it in the utils module's namespace
        import src.utils
        original_create_no_window = getattr(src.utils.subprocess, 'CREATE_NO_WINDOW', None)
        src.utils.subprocess.CREATE_NO_WINDOW = 0x08000000
        
        try:
            mock_check_output.return_value = b"aws-cli/2.0.0"
            
            result = check_aws_dependencies()
            
            assert result is True
            assert mock_check_output.call_count == 2
        finally:
            # Restore original state
            if original_create_no_window is None:
                if hasattr(src.utils.subprocess, 'CREATE_NO_WINDOW'):
                    delattr(src.utils.subprocess, 'CREATE_NO_WINDOW')
            else:
                src.utils.subprocess.CREATE_NO_WINDOW = original_create_no_window
    
    def test_check_aws_dependencies_missing_cli(self, mocker):
        """Test missing AWS CLI"""
        mock_check_output = mocker.patch('src.utils.subprocess.check_output')
        mock_check_output.side_effect = FileNotFoundError()
        
        result = check_aws_dependencies()
        
        assert result is False
    
    def test_check_aws_dependencies_missing_plugin(self, mocker):
        """Test missing Session Manager Plugin"""
        mock_check_output = mocker.patch('src.utils.subprocess.check_output')
        # First call succeeds (AWS CLI), second fails (plugin)
        mock_check_output.side_effect = [
            b"aws-cli/2.0.0",
            subprocess.CalledProcessError(1, "aws")
        ]
        
        result = check_aws_dependencies()
        
        assert result is False


class TestValidateRemoteHost:
    """Tests for validate_remote_host function"""
    
    def test_validate_remote_host_valid(self):
        """Test valid hostnames"""
        assert validate_remote_host("example.com") is True
        assert validate_remote_host("192.168.1.1") is True
        assert validate_remote_host("host-name.example") is True
        assert validate_remote_host("host_name") is True
        assert validate_remote_host("localhost") is True
    
    def test_validate_remote_host_invalid(self):
        """Test invalid hostnames"""
        assert validate_remote_host("") is False
        assert validate_remote_host("host@name") is False
        assert validate_remote_host("host name") is False
        assert validate_remote_host("host!name") is False
        assert validate_remote_host(None) is False


class TestValidatePort:
    """Tests for validate_port function"""
    
    def test_validate_port_valid(self):
        """Test valid ports"""
        assert validate_port(1) is True
        assert validate_port(22) is True
        assert validate_port(3389) is True
        assert validate_port(65535) is True
        assert validate_port(60000) is True
    
    def test_validate_port_invalid(self):
        """Test invalid ports"""
        assert validate_port(0) is False
        assert validate_port(65536) is False
        assert validate_port(-1) is False
        assert validate_port("22") is False  # String instead of int
        assert validate_port(None) is False


class TestWhich:
    """Tests for which function"""
    
    @patch('src.utils.shutil.which')
    def test_which_found(self, mock_which):
        """Test finding a command"""
        mock_which.return_value = "/usr/bin/python"
        
        result = which("python")
        
        assert result == "/usr/bin/python"
        mock_which.assert_called_once_with("python")
    
    @patch('src.utils.shutil.which')
    def test_which_not_found(self, mock_which):
        """Test not finding a command"""
        mock_which.return_value = None
        
        result = which("nonexistent")
        
        assert result is None


class TestRequireCmd:
    """Tests for require_cmd function"""
    
    @patch('src.utils.shutil.which')
    def test_require_cmd_found(self, mock_which):
        """Test requiring a command that exists"""
        mock_which.return_value = "/usr/bin/python"
        
        # Should not raise
        require_cmd("python", "Python interpreter")
    
    @patch('src.utils.shutil.which')
    def test_require_cmd_not_found(self, mock_which):
        """Test requiring a command that doesn't exist"""
        mock_which.return_value = None
        
        with pytest.raises(RuntimeError, match="Required tool 'python' not found"):
            require_cmd("python", "Python interpreter")
