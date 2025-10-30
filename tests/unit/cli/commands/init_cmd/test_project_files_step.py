"""
Unit tests for project_files_step.py
Target: Increase coverage from 75% to 80%+
"""

from cli.commands.init_cmd.project_files_step import create_project_files


class TestCreateProjectFiles:
    """Test create_project_files function"""

    def test_successful_file_creation(self, temp_project_dir, mocker):
        """Test successful creation of all project files"""
        mock_echo = mocker.patch("click.echo")
        
        # Create src directory first
        (temp_project_dir / "src").mkdir(exist_ok=True)
        
        result = create_project_files(temp_project_dir)
        
        assert result is True
        
        # Verify files were created
        assert (temp_project_dir / "src" / "__init__.py").exists()
        assert (temp_project_dir / "requirements.txt").exists()
        
        # Verify content
        init_content = (temp_project_dir / "src" / "__init__.py").read_text()
        assert "# Source directory" in init_content
        
        req_content = (temp_project_dir / "requirements.txt").read_text()
        assert "solace-agent-mesh" in req_content

    def test_requirements_txt_version(self, temp_project_dir, mocker):
        """Test that requirements.txt contains correct version"""
        mock_echo = mocker.patch("click.echo")
        mock_version = mocker.patch("cli.commands.init_cmd.project_files_step.cli_version", "1.2.3")
        
        (temp_project_dir / "src").mkdir(exist_ok=True)
        
        create_project_files(temp_project_dir)
        
        req_content = (temp_project_dir / "requirements.txt").read_text()
        assert "solace-agent-mesh~=1.2.3" in req_content

    def test_init_file_creation_failure(self, temp_project_dir, mocker):
        """Test handling of __init__.py creation failure"""
        mock_echo = mocker.patch("click.echo")
        
        # Don't create src directory to cause failure
        result = create_project_files(temp_project_dir)
        
        assert result is False
        
        # Verify error message was displayed
        echo_calls = [str(call) for call in mock_echo.call_args_list]
        assert any("Error creating file" in call for call in echo_calls)

    def test_requirements_file_creation_failure(self, temp_project_dir, mocker):
        """Test handling of requirements.txt creation failure"""
        mock_echo = mocker.patch("click.echo")
        
        # Create src directory
        (temp_project_dir / "src").mkdir(exist_ok=True)
        
        # Mock open to fail for requirements.txt
        original_open = open
        def mock_open(file, *args, **kwargs):
            if "requirements.txt" in str(file):
                raise IOError("Permission denied")
            return original_open(file, *args, **kwargs)
        
        mocker.patch("builtins.open", mock_open)
        
        result = create_project_files(temp_project_dir)
        
        assert result is False

    def test_messages_displayed(self, temp_project_dir, mocker):
        """Test that appropriate messages are displayed"""
        mock_echo = mocker.patch("click.echo")
        
        (temp_project_dir / "src").mkdir(exist_ok=True)
        
        create_project_files(temp_project_dir)
        
        echo_calls = [str(call) for call in mock_echo.call_args_list]
        assert any("Creating project files" in call for call in echo_calls)
        assert any("__init__.py" in call for call in echo_calls)
        assert any("requirements.txt" in call for call in echo_calls)

    def test_files_overwritten_if_exist(self, temp_project_dir, mocker):
        """Test that existing files are overwritten"""
        mock_echo = mocker.patch("click.echo")
        
        (temp_project_dir / "src").mkdir(exist_ok=True)
        
        # Create existing files with different content
        (temp_project_dir / "src" / "__init__.py").write_text("old content")
        (temp_project_dir / "requirements.txt").write_text("old requirements")
        
        result = create_project_files(temp_project_dir)
        
        assert result is True
        
        # Verify files were overwritten with new content
        init_content = (temp_project_dir / "src" / "__init__.py").read_text()
        assert "# Source directory" in init_content
        assert "old content" not in init_content