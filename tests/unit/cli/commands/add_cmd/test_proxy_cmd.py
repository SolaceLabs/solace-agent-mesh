import pytest
from pathlib import Path
from click.testing import CliRunner
from cli.commands.add_cmd.proxy_cmd import add_proxy


class TestAddProxy:
    """Test suite for the 'sam add proxy' command"""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def project_dir(self, tmp_path):
        """Create a temporary project directory"""
        project = tmp_path / "test_project"
        project.mkdir()
        
        # Create templates directory with proxy_template.yaml
        templates_dir = project / "templates"
        templates_dir.mkdir()
        
        proxy_template = templates_dir / "proxy_template.yaml"
        proxy_template.write_text("""# A2A Proxy Configuration File

log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: a2a_proxy.log

# Shared SAM config (includes broker connection details)
!include shared_config.yaml

apps:
  - name: "__PROXY_NAME____app"
    app_base_path: .
    app_module: src.solace_agent_mesh.agent.proxies.a2a.app 
    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      artifact_service:
        type: "filesystem"
        base_path: "/tmp/samv2"
        artifact_scope: namespace
      artifact_handling_mode: "reference"
      discovery_interval_seconds: 5
      tools:
        - group_name: artifact_management
          tool_type: builtin-group
      proxied_agents:
        - name: "HelloWorld"
          url: "http://localhost:9999"
        - name: "AnalysisAgent"
          url: "http://127.0.0.1:10001"
""")
        
        return project

    @pytest.fixture
    def mock_template(self, mocker, project_dir):
        """Mock the load_template function"""
        def load_template_side_effect(name):
            if name == "proxy_template.yaml":
                return """# A2A Proxy Configuration File

log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: a2a_proxy.log

apps:
  - name: "__PROXY_NAME____app"
    app_base_path: .
"""
            else:
                raise FileNotFoundError(f"Template {name} not found")
        
        return mocker.patch(
            "cli.commands.add_cmd.proxy_cmd.load_template",
            side_effect=load_template_side_effect
        )

    def test_add_proxy_with_name_and_skip(self, runner, project_dir, mock_template, mocker):
        """Test add proxy with name and --skip flag"""
        mocker.patch("cli.commands.add_cmd.proxy_cmd.Path.cwd", return_value=project_dir)
        
        result = runner.invoke(add_proxy, ["TestProxy", "--skip"])
        
        assert result.exit_code == 0
        assert "Proxy configuration created" in result.output
        
        # Verify file was created
        expected_file = project_dir / "configs" / "agents" / "test_proxy_proxy.yaml"
        assert expected_file.exists()

    def test_add_proxy_missing_name(self, runner):
        """Test that missing name shows error"""
        result = runner.invoke(add_proxy, ["--skip"])
        
        assert "Error: You must provide a proxy name" in result.output

    def test_add_proxy_replaces_placeholder(self, runner, project_dir, mock_template, mocker):
        """Test that __PROXY_NAME__ placeholder is replaced correctly"""
        mocker.patch("cli.commands.add_cmd.proxy_cmd.Path.cwd", return_value=project_dir)
        
        result = runner.invoke(add_proxy, ["MyAwesomeProxy", "--skip"])
        
        assert result.exit_code == 0
        
        # Check that file was created
        proxy_file = project_dir / "configs" / "agents" / "my_awesome_proxy_proxy.yaml"
        assert proxy_file.exists()
        
        # Check that placeholder was replaced
        content = proxy_file.read_text()
        assert "__PROXY_NAME__" not in content
        assert "MyAwesomeProxy" in content
        assert 'name: "MyAwesomeProxy__app"' in content

    def test_add_proxy_file_naming(self, runner, project_dir, mock_template, mocker):
        """Test that proxy file uses snake_case naming"""
        mocker.patch("cli.commands.add_cmd.proxy_cmd.Path.cwd", return_value=project_dir)

        test_cases = [
            ("SimpleProxy", "simple_proxy_proxy.yaml"),
            ("my-proxy", "my_proxy_proxy.yaml"),
            ("ProxyAgent123", "proxy_agent123_proxy.yaml"),
        ]

        for input_name, expected_filename in test_cases:
            result = runner.invoke(add_proxy, [input_name, "--skip"])
            assert result.exit_code == 0

            proxy_file = project_dir / "configs" / "agents" / expected_filename
            assert proxy_file.exists(), f"Expected file {expected_filename} not found for input {input_name}"

    def test_add_proxy_creates_directory(self, runner, project_dir, mock_template, mocker):
        """Test that configs/agents directory is created if it doesn't exist"""
        mocker.patch("cli.commands.add_cmd.proxy_cmd.Path.cwd", return_value=project_dir)
        
        agents_dir = project_dir / "configs" / "agents"
        assert not agents_dir.exists()
        
        result = runner.invoke(add_proxy, ["TestProxy", "--skip"])
        
        assert result.exit_code == 0
        assert agents_dir.exists()
        assert agents_dir.is_dir()

    def test_add_proxy_template_not_found(self, runner, project_dir, mocker):
        """Test error handling when template is not found"""
        mocker.patch("cli.commands.add_cmd.proxy_cmd.Path.cwd", return_value=project_dir)
        mocker.patch(
            "cli.commands.add_cmd.proxy_cmd.load_template",
            side_effect=FileNotFoundError("Template not found")
        )
        
        result = runner.invoke(add_proxy, ["TestProxy", "--skip"])
        
        assert "Error: Template file 'proxy_template.yaml' not found" in result.output

    def test_add_proxy_without_skip_flag(self, runner, project_dir, mock_template, mocker):
        """Test add proxy without --skip flag (should work the same)"""
        mocker.patch("cli.commands.add_cmd.proxy_cmd.Path.cwd", return_value=project_dir)
        
        result = runner.invoke(add_proxy, ["TestProxy"])
        
        assert result.exit_code == 0
        assert "Proxy configuration created" in result.output
        
        # Verify file was created
        expected_file = project_dir / "configs" / "agents" / "test_proxy_proxy.yaml"
        assert expected_file.exists()

    def test_add_proxy_pascal_case_conversion(self, runner, project_dir, mock_template, mocker):
        """Test that various naming formats convert to PascalCase correctly"""
        mocker.patch("cli.commands.add_cmd.proxy_cmd.Path.cwd", return_value=project_dir)
        
        test_cases = [
            ("hello_world", "HelloWorld"),
            ("hello-world", "HelloWorld"),
            ("helloWorld", "HelloWorld"),
            ("HELLO_WORLD", "HelloWorld"),
            ("api_proxy", "ApiProxy"),
        ]
        
        for input_name, expected_pascal in test_cases:
            result = runner.invoke(add_proxy, [input_name, "--skip"])
            assert result.exit_code == 0
            
            # Find the created file
            agents_dir = project_dir / "configs" / "agents"
            proxy_files = list(agents_dir.glob("*.yaml"))
            
            # Read the most recently created file
            if proxy_files:
                latest_file = max(proxy_files, key=lambda p: p.stat().st_mtime)
                content = latest_file.read_text()
                assert f'name: "{expected_pascal}__app"' in content, \
                    f"Expected {expected_pascal} in file for input {input_name}"

    def test_add_proxy_success_message(self, runner, project_dir, mock_template, mocker):
        """Test that success message contains only the creation message"""
        mocker.patch("cli.commands.add_cmd.proxy_cmd.Path.cwd", return_value=project_dir)
        
        result = runner.invoke(add_proxy, ["TestProxy", "--skip"])
        
        assert result.exit_code == 0
        assert "Proxy configuration created" in result.output