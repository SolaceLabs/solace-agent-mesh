
"""
Unit tests for broker_step.py
Target: Increase coverage from 32% to 80%+
"""
import pytest
from cli.commands.init_cmd.broker_step import broker_setup_step


class TestBrokerSetupStep:
    """Test broker_setup_step function"""

    def test_existing_solace_broker_type_1(self, mocker, mock_shutil_which):
        """Test existing Solace broker with type '1'"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.broker_step.ask_if_not_provided")
        
        # ask_if_not_provided updates options dict in place and returns the value
        def ask_side_effect(opts, key, *args, **kwargs):
            values = {
                "broker_type": "1",
                "broker_url": "ws://broker.example.com:8008",
                "broker_vpn": "my_vpn",
                "broker_username": "my_user",
                "broker_password": "my_pass",
            }
            opts[key] = values[key]
            return values[key]
        
        mock_ask.side_effect = ask_side_effect
        
        options = {}
        default_values = {"broker_type": "1"}
        
        result = broker_setup_step(options, default_values, skip_interactive=False)
        
        assert result["broker_type"] == "1"
        assert result["dev_mode"] == "false"
        assert result["broker_url"] == "ws://broker.example.com:8008"
        assert result["broker_vpn"] == "my_vpn"
        assert result["broker_username"] == "my_user"
        assert result["broker_password"] == "my_pass"

    def test_existing_solace_broker_type_solace(self, mocker, mock_shutil_which):
        """Test existing Solace broker with type 'solace'"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.broker_step.ask_if_not_provided")
        mock_ask.side_effect = [
            "solace",
            "ws://solace.broker:8008",
            "vpn_name",
            "username",
            "password",
        ]
        
        options = {}
        default_values = {}
        
        result = broker_setup_step(options, default_values, skip_interactive=False)
        
        assert result["broker_type"] == "solace"
        assert result["dev_mode"] == "false"

    def test_container_broker_with_podman(self, mocker, mock_subprocess):
        """Test container broker setup with Podman"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.broker_step.ask_if_not_provided")
        mock_ask.side_effect = ["2", "podman"]
        
        mock_which = mocker.patch("shutil.which")
        mock_which.side_effect = lambda cmd: "/usr/bin/podman" if cmd == "podman" else None
        
        mock_confirm = mocker.patch("click.confirm", return_value=True)
        
        options = {}
        default_values = {
            "SOLACE_LOCAL_BROKER_URL": "ws://localhost:8008",
            "SOLACE_LOCAL_BROKER_VPN": "default",
            "SOLACE_LOCAL_BROKER_USERNAME": "default",
            "SOLACE_LOCAL_BROKER_PASSWORD": "default",
        }
        
        result = broker_setup_step(options, default_values, skip_interactive=False)
        
        assert result["broker_type"] == "2"
        assert result["dev_mode"] == "false"
        assert result["container_engine"] == "podman"
        assert result["broker_url"] == "ws://localhost:8008"
        mock_subprocess.assert_called_once()

    def test_container_broker_with_docker(self, mocker, mock_subprocess):
        """Test container broker setup with Docker"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.broker_step.ask_if_not_provided")
        mock_ask.side_effect = ["container", "docker"]
        
        mock_which = mocker.patch("shutil.which")
        mock_which.side_effect = lambda cmd: "/usr/bin/docker" if cmd == "docker" else None
        
        mock_confirm = mocker.patch("click.confirm", return_value=True)
        
        options = {}
        default_values = {
            "SOLACE_LOCAL_BROKER_URL": "ws://localhost:8008",
            "SOLACE_LOCAL_BROKER_VPN": "default",
            "SOLACE_LOCAL_BROKER_USERNAME": "default",
            "SOLACE_LOCAL_BROKER_PASSWORD": "default",
        }
        
        result = broker_setup_step(options, default_values, skip_interactive=False)
        
        assert result["container_engine"] == "docker"
        mock_subprocess.assert_called_once()

    def test_container_broker_no_engine_available(self, mocker):
        """Test container broker when neither Podman nor Docker is available"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.broker_step.ask_if_not_provided")
        mock_ask.return_value = "2"
        
        mock_which = mocker.patch("shutil.which", return_value=None)
        
        options = {}
        default_values = {}
        
        with pytest.raises(SystemExit):
            broker_setup_step(options, default_values, skip_interactive=False)

    def test_container_broker_user_declines_execution(self, mocker):
        """Test container broker when user declines container execution"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.broker_step.ask_if_not_provided")
        mock_ask.side_effect = [
            "2",
            "podman",
            "ws://manual.broker:8008",
            "manual_vpn",
            "manual_user",
            "manual_pass",
        ]
        
        mock_which = mocker.patch("shutil.which")
        mock_which.side_effect = lambda cmd: "/usr/bin/podman" if cmd == "podman" else None
        
        mock_confirm = mocker.patch("click.confirm", return_value=False)
        
        options = {}
        default_values = {}
        
        result = broker_setup_step(options, default_values, skip_interactive=False)
        
        assert result["broker_url"] == "ws://manual.broker:8008"
        assert result["broker_vpn"] == "manual_vpn"

    def test_container_broker_skip_interactive(self, mocker, mock_subprocess):
        """Test container broker in skip interactive mode"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.broker_step.ask_if_not_provided")
        mock_ask.side_effect = ["2", "docker"]
        
        mock_which = mocker.patch("shutil.which")
        mock_which.side_effect = lambda cmd: "/usr/bin/docker" if cmd == "docker" else None
        
        options = {}
        default_values = {
            "SOLACE_LOCAL_BROKER_URL": "ws://localhost:8008",
            "SOLACE_LOCAL_BROKER_VPN": "default",
            "SOLACE_LOCAL_BROKER_USERNAME": "default",
            "SOLACE_LOCAL_BROKER_PASSWORD": "default",
        }
        
        result = broker_setup_step(options, default_values, skip_interactive=True)
        
        assert result["broker_url"] == "ws://localhost:8008"
        mock_subprocess.assert_called_once()

    def test_container_broker_command_fails(self, mocker):
        """Test container broker when command execution fails"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.broker_step.ask_if_not_provided")
        mock_ask.side_effect = ["2", "podman"]
        
        mock_which = mocker.patch("shutil.which")
        mock_which.side_effect = lambda cmd: "/usr/bin/podman" if cmd == "podman" else None
        
        mock_confirm = mocker.patch("click.confirm", return_value=True)
        mock_system = mocker.patch("os.system", return_value=1)  # Non-zero exit code
        
        options = {}
        default_values = {}
        
        with pytest.raises(SystemExit):
            broker_setup_step(options, default_values, skip_interactive=False)

    def test_container_broker_exception_during_execution(self, mocker):
        """Test container broker when exception occurs during execution"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.broker_step.ask_if_not_provided")
        mock_ask.side_effect = ["2", "docker"]
        
        mock_which = mocker.patch("shutil.which")
        mock_which.side_effect = lambda cmd: "/usr/bin/docker" if cmd == "docker" else None
        
        mock_confirm = mocker.patch("click.confirm", return_value=True)
        mock_system = mocker.patch("os.system", side_effect=Exception("System error"))
        
        options = {}
        default_values = {}
        
        with pytest.raises(SystemExit):
            broker_setup_step(options, default_values, skip_interactive=False)

    def test_dev_mode_type_3(self, mocker):
        """Test dev mode with type '3'"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.broker_step.ask_if_not_provided")
        mock_ask.return_value = "3"
        
        options = {}
        default_values = {
            "DEV_BROKER_URL": "INTERNAL_DEV_BROKER",
            "DEV_BROKER_VPN": "dev_vpn",
            "DEV_BROKER_USERNAME": "dev_user",
            "DEV_BROKER_PASSWORD": "dev_pass",
        }
        
        result = broker_setup_step(options, default_values, skip_interactive=False)
        
        assert result["broker_type"] == "3"
        assert result["dev_mode"] == "true"
        assert result["broker_url"] == "INTERNAL_DEV_BROKER"
        assert result["broker_vpn"] == "dev_vpn"
        assert result["broker_username"] == "dev_user"
        assert result["broker_password"] == "dev_pass"

    def test_dev_mode_type_dev(self, mocker):
        """Test dev mode with type 'dev'"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.broker_step.ask_if_not_provided")
        mock_ask.return_value = "dev"
        
        options = {}
        default_values = {
            "DEV_BROKER_URL": "INTERNAL_DEV_BROKER",
            "DEV_BROKER_VPN": "dev_vpn",
            "DEV_BROKER_USERNAME": "dev_user",
            "DEV_BROKER_PASSWORD": "dev_pass",
        }
        
        result = broker_setup_step(options, default_values, skip_interactive=False)
        
        assert result["dev_mode"] == "true"

    def test_dev_mode_type_dev_broker(self, mocker):
        """Test dev mode with type 'dev_broker'"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.broker_step.ask_if_not_provided")
        mock_ask.return_value = "dev_broker"
        
        options = {}
        default_values = {
            "DEV_BROKER_URL": "INTERNAL_DEV_BROKER",
            "DEV_BROKER_VPN": "dev_vpn",
            "DEV_BROKER_USERNAME": "dev_user",
            "DEV_BROKER_PASSWORD": "dev_pass",
        }
        
        result = broker_setup_step(options, default_values, skip_interactive=False)
        
        assert result["dev_mode"] == "true"

    def test_dev_mode_type_dev_mode(self, mocker):
        """Test dev mode with type 'dev_mode'"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.broker_step.ask_if_not_provided")
        mock_ask.return_value = "dev_mode"
        
        options = {}
        default_values = {
            "DEV_BROKER_URL": "INTERNAL_DEV_BROKER",
            "DEV_BROKER_VPN": "dev_vpn",
            "DEV_BROKER_USERNAME": "dev_user",
            "DEV_BROKER_PASSWORD": "dev_pass",
        }
        
        result = broker_setup_step(options, default_values, skip_interactive=False)
        
        assert result["dev_mode"] == "true"

    def test_broker_with_provided_options(self, mocker):
        """Test broker setup with pre-provided options"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.broker_step.ask_if_not_provided")
        mock_ask.return_value = "1"
        
        options = {
            "broker_type": "1",
            "broker_url": "ws://provided.broker:8008",
            "broker_vpn": "provided_vpn",
            "broker_username": "provided_user",
            "broker_password": "provided_pass",
        }
        default_values = {}
        
        result = broker_setup_step(options, default_values, skip_interactive=True)
        
        # Should use provided values
        assert result["broker_url"] == "ws://provided.broker:8008"
        assert result["broker_vpn"] == "provided_vpn"

    def test_container_engine_default_selection(self, mocker, mock_subprocess):
        """Test container engine defaults to podman when both available"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.broker_step.ask_if_not_provided")
        mock_ask.side_effect = ["2", "podman"]
        
        mock_which = mocker.patch("shutil.which")
        mock_which.return_value = "/usr/bin/podman"  # Both available
        
        mock_confirm = mocker.patch("click.confirm", return_value=True)
        
        options = {}
        default_values = {
            "SOLACE_LOCAL_BROKER_URL": "ws://localhost:8008",
            "SOLACE_LOCAL_BROKER_VPN": "default",
            "SOLACE_LOCAL_BROKER_USERNAME": "default",
            "SOLACE_LOCAL_BROKER_PASSWORD": "default",
        }
        
        result = broker_setup_step(options, default_values, skip_interactive=False)
        
        # Verify podman was selected as default
        assert result["container_engine"] == "podman"

    def test_container_engine_docker_when_podman_unavailable(self, mocker, mock_subprocess):
        """Test container engine defaults to docker when podman unavailable"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.broker_step.ask_if_not_provided")
        mock_ask.side_effect = ["2", "docker"]
        
        mock_which = mocker.patch("shutil.which")
        mock_which.side_effect = lambda cmd: "/usr/bin/docker" if cmd == "docker" else None
        
        mock_confirm = mocker.patch("click.confirm", return_value=True)
        
        options = {}
        default_values = {
            "SOLACE_LOCAL_BROKER_URL": "ws://localhost:8008",
            "SOLACE_LOCAL_BROKER_VPN": "default",
            "SOLACE_LOCAL_BROKER_USERNAME": "default",
            "SOLACE_LOCAL_BROKER_PASSWORD": "default",
        }
        
        result = broker_setup_step(options, default_values, skip_interactive=False)
        
        # Verify docker was selected as default
        assert result["container_engine"] == "docker"

    def test_broker_messages_displayed(self, mocker):
        """Test that appropriate messages are displayed"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.broker_step.ask_if_not_provided")
        mock_ask.return_value = "dev"
        
        options = {}
        default_values = {
            "DEV_BROKER_URL": "INTERNAL_DEV_BROKER",
            "DEV_BROKER_VPN": "dev_vpn",
            "DEV_BROKER_USERNAME": "dev_user",
            "DEV_BROKER_PASSWORD": "dev_pass",
        }
        
        broker_setup_step(options, default_values, skip_interactive=False)
        
        # Verify key messages were displayed
        echo_calls = [str(call) for call in mock_echo.call_args_list]
        assert any("Configuring Broker" in call for call in echo_calls)
        assert any("Dev mode selected" in call for call in echo_calls)