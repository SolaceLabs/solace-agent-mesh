"""
Unit tests for directory_step.py
Target: Increase coverage from 77% to 80%+
"""
from pathlib import Path

from cli.commands.init_cmd.directory_step import create_project_directories


class TestCreateProjectDirectories:
    """Test create_project_directories function"""

    def test_successful_directory_creation(self, temp_project_dir, mocker):
        """Test successful creation of all project directories"""
        mock_echo = mocker.patch("click.echo")
        
        result = create_project_directories(temp_project_dir)
        
        assert result is True
        
        # Verify all directories were created
        assert (temp_project_dir / "configs").exists()
        assert (temp_project_dir / "configs" / "gateways").exists()
        assert (temp_project_dir / "configs" / "agents").exists()
        assert (temp_project_dir / "src").exists()
        
        # Verify messages were displayed
        echo_calls = [str(call) for call in mock_echo.call_args_list]
        assert any("Creating directory structure" in call for call in echo_calls)

    def test_directory_creation_with_existing_dirs(self, temp_project_dir, mocker):
        """Test directory creation when some directories already exist"""
        mock_echo = mocker.patch("click.echo")
        
        # Pre-create some directories
        (temp_project_dir / "configs").mkdir()
        (temp_project_dir / "src").mkdir()
        
        result = create_project_directories(temp_project_dir)
        
        assert result is True
        # All directories should still exist
        assert (temp_project_dir / "configs" / "gateways").exists()
        assert (temp_project_dir / "configs" / "agents").exists()

    def test_directory_creation_failure(self, temp_project_dir, mocker):
        """Test directory creation failure handling"""
        mock_echo = mocker.patch("click.echo")
        
        # Mock mkdir to raise OSError
        original_mkdir = Path.mkdir
        def mock_mkdir(self, *args, **kwargs):
            if "gateways" in str(self):
                raise OSError("Permission denied")
            return original_mkdir(self, *args, **kwargs)
        
        mocker.patch.object(Path, "mkdir", mock_mkdir)
        
        result = create_project_directories(temp_project_dir)
        
        assert result is False
        
        # Verify error message was displayed
        echo_calls = [str(call) for call in mock_echo.call_args_list]
        assert any("Error creating directory" in call for call in echo_calls)

    def test_all_required_directories_created(self, temp_project_dir, mocker):
        """Test that all required directories are in the list"""
        mock_echo = mocker.patch("click.echo")
        
        create_project_directories(temp_project_dir)
        
        # Verify specific directory structure
        assert (temp_project_dir / "configs").is_dir()
        assert (temp_project_dir / "configs" / "gateways").is_dir()
        assert (temp_project_dir / "configs" / "agents").is_dir()
        assert (temp_project_dir / "src").is_dir()

    def test_directory_creation_messages(self, temp_project_dir, mocker):
        """Test that appropriate messages are displayed for each directory"""
        mock_echo = mocker.patch("click.echo")
        
        create_project_directories(temp_project_dir)
        
        echo_calls = [str(call) for call in mock_echo.call_args_list]
        
        # Verify messages for each directory
        assert any("configs" in call for call in echo_calls)
        assert any("gateways" in call for call in echo_calls)
        assert any("agents" in call for call in echo_calls)
        assert any("src" in call for call in echo_calls)