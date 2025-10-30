"""
Unit tests for database_step.py
Target: Increase coverage from 12% to 80%+
"""
import pytest

from cli.commands.init_cmd.database_step import (
    prompt_for_db_credentials,
    database_setup_step,
)


class TestPromptForDbCredentials:
    """Test prompt_for_db_credentials function"""

    def test_skip_interactive_with_provided_url(self, mocker):
        """Test non-interactive mode with provided database URL"""
        options = {"orchestrator_database_url": "postgresql://user:pass@localhost/db"}
        result = prompt_for_db_credentials(options, "orchestrator", skip_interactive=True)
        
        assert result == "postgresql://user:pass@localhost/db"

    def test_skip_interactive_without_url_raises_error(self):
        """Test non-interactive mode without database URL raises ValueError"""
        options = {}
        
        with pytest.raises(ValueError, match="Database URL for orchestrator is required"):
            prompt_for_db_credentials(options, "orchestrator", skip_interactive=True)

    def test_interactive_postgresql_selection(self, mocker):
        """Test interactive mode with PostgreSQL selection"""
        mock_ask = mocker.patch("cli.commands.init_cmd.database_step.ask_if_not_provided")
        mock_ask.side_effect = [
            "postgresql",  # db_backend choice
            "postgresql://user:pass@localhost:5432/testdb"  # PostgreSQL URL
        ]
        
        options = {}
        result = prompt_for_db_credentials(options, "gateway", skip_interactive=False)
        
        assert result == "postgresql://user:pass@localhost:5432/testdb"
        assert mock_ask.call_count == 2

    def test_interactive_sqlite_selection(self, mocker):
        """Test interactive mode with SQLite selection"""
        mock_ask = mocker.patch("cli.commands.init_cmd.database_step.ask_if_not_provided")
        mock_ask.return_value = "sqlite"
        
        options = {}
        result = prompt_for_db_credentials(options, "gateway", skip_interactive=False)
        
        assert result is None  # SQLite returns None for default handling
        mock_ask.assert_called_once()

    def test_interactive_with_existing_url_in_options(self, mocker):
        """Test interactive mode when URL already exists in options"""
        mock_ask = mocker.patch("cli.commands.init_cmd.database_step.ask_if_not_provided")
        mock_ask.side_effect = [
            "postgresql",
            "postgresql://existing:url@host/db"
        ]
        
        options = {"gateway_database_url": "postgresql://old:url@host/db"}
        result = prompt_for_db_credentials(options, "gateway", skip_interactive=False)
        
        assert result == "postgresql://existing:url@host/db"


class TestDatabaseSetupStep:
    """Test database_setup_step function"""

    def test_no_databases_configured(self, temp_project_dir, mocker):
        """Test when no databases are configured"""
        mock_echo = mocker.patch("click.echo")
        options = {}
        
        result = database_setup_step(temp_project_dir, options, skip_interactive=True)
        
        assert result is True
        mock_echo.assert_any_call("Setting up database(s)...")
        mock_echo.assert_any_call("  Database setup complete.")

    def test_webui_gateway_with_provided_url(self, temp_project_dir, mocker, mock_database_operations):
        """Test WebUI gateway database setup with provided URL"""
        mock_echo = mocker.patch("click.echo")
        mock_validate = mocker.patch("cli.commands.init_cmd.database_step.create_and_validate_database")
        
        options = {
            "add_webui_gateway": True,
            "web_ui_gateway_database_url": "postgresql://user:pass@localhost/webui"
        }
        
        result = database_setup_step(temp_project_dir, options, skip_interactive=True)
        
        assert result is True
        assert options["web_ui_gateway_database_url"] == "postgresql://user:pass@localhost/webui"
        mock_validate.assert_called_once_with(
            "postgresql://user:pass@localhost/webui",
            "web_ui_gateway_database_url database"
        )

    def test_webui_gateway_default_sqlite(self, temp_project_dir, mocker, mock_database_operations):
        """Test WebUI gateway with default SQLite database"""
        mock_echo = mocker.patch("click.echo")
        mock_validate = mocker.patch("cli.commands.init_cmd.database_step.create_and_validate_database")
        
        options = {"add_webui_gateway": True}
        
        result = database_setup_step(temp_project_dir, options, skip_interactive=True)
        
        assert result is True
        assert "web_ui_gateway_database_url" in options
        assert "sqlite:///" in options["web_ui_gateway_database_url"]
        assert "webui_gateway.db" in options["web_ui_gateway_database_url"]
        
        # Verify data directory was created
        data_dir = temp_project_dir / "data"
        assert data_dir.exists()
        
        mock_validate.assert_called_once()

    def test_orchestrator_with_provided_url(self, temp_project_dir, mocker, mock_database_operations):
        """Test orchestrator database setup with provided URL"""
        mock_echo = mocker.patch("click.echo")
        mock_validate = mocker.patch("cli.commands.init_cmd.database_step.create_and_validate_database")
        
        options = {
            "use_orchestrator_db": True,
            "agent_name": "TestAgent",
            "orchestrator_database_url": "postgresql://user:pass@localhost/orch"
        }
        
        result = database_setup_step(temp_project_dir, options, skip_interactive=True)
        
        assert result is True
        assert options["orchestrator_database_url"] == "postgresql://user:pass@localhost/orch"
        mock_validate.assert_called_once()

    def test_orchestrator_default_sqlite_with_agent_name(self, temp_project_dir, mocker, mock_database_operations):
        """Test orchestrator with default SQLite using agent name"""
        mock_echo = mocker.patch("click.echo")
        mock_validate = mocker.patch("cli.commands.init_cmd.database_step.create_and_validate_database")
        
        options = {
            "use_orchestrator_db": True,
            "agent_name": "MyTestAgent"
        }
        
        result = database_setup_step(temp_project_dir, options, skip_interactive=True)
        
        assert result is True
        assert "orchestrator_database_url" in options
        assert "mytestagent.db" in options["orchestrator_database_url"]
        mock_validate.assert_called_once()

    def test_interactive_user_chooses_own_database(self, temp_project_dir, mocker, mock_database_operations):
        """Test interactive mode when user chooses their own database"""
        mock_echo = mocker.patch("click.echo")
        mock_ask_yes_no = mocker.patch("cli.commands.init_cmd.database_step.ask_yes_no_question", return_value=True)
        mock_prompt = mocker.patch(
            "cli.commands.init_cmd.database_step.prompt_for_db_credentials",
            return_value="postgresql://custom:db@host/name"
        )
        mock_validate = mocker.patch("cli.commands.init_cmd.database_step.create_and_validate_database")
        
        options = {"add_webui_gateway": True}
        
        result = database_setup_step(temp_project_dir, options, skip_interactive=False)
        
        assert result is True
        assert options["web_ui_gateway_database_url"] == "postgresql://custom:db@host/name"
        mock_ask_yes_no.assert_called_once()
        mock_prompt.assert_called_once()
        mock_validate.assert_called_once()

    def test_interactive_user_declines_own_database(self, temp_project_dir, mocker, mock_database_operations):
        """Test interactive mode when user declines their own database"""
        mock_echo = mocker.patch("click.echo")
        mock_ask_yes_no = mocker.patch("cli.commands.init_cmd.database_step.ask_yes_no_question", return_value=False)
        mock_validate = mocker.patch("cli.commands.init_cmd.database_step.create_and_validate_database")
        
        options = {"add_webui_gateway": True}
        
        result = database_setup_step(temp_project_dir, options, skip_interactive=False)
        
        assert result is True
        assert "sqlite:///" in options["web_ui_gateway_database_url"]
        mock_ask_yes_no.assert_called_once()
        mock_validate.assert_called_once()

    def test_both_databases_configured(self, temp_project_dir, mocker, mock_database_operations):
        """Test when both WebUI gateway and orchestrator databases are configured"""
        mock_echo = mocker.patch("click.echo")
        mock_validate = mocker.patch("cli.commands.init_cmd.database_step.create_and_validate_database")
        
        options = {
            "add_webui_gateway": True,
            "use_orchestrator_db": True,
            "agent_name": "TestOrch"
        }
        
        result = database_setup_step(temp_project_dir, options, skip_interactive=True)
        
        assert result is True
        assert "web_ui_gateway_database_url" in options
        assert "orchestrator_database_url" in options
        assert mock_validate.call_count == 2

    def test_database_validation_called_correctly(self, temp_project_dir, mocker, mock_database_operations):
        """Test that database validation is called with correct parameters"""
        mock_echo = mocker.patch("click.echo")
        mock_validate = mocker.patch("cli.commands.init_cmd.database_step.create_and_validate_database")
        
        options = {
            "add_webui_gateway": True,
            "web_ui_gateway_database_url": "sqlite:///test.db"
        }
        
        database_setup_step(temp_project_dir, options, skip_interactive=True)
        
        mock_validate.assert_called_once_with(
            "sqlite:///test.db",
            "web_ui_gateway_database_url database"
        )

    def test_data_directory_creation(self, temp_project_dir, mocker, mock_database_operations):
        """Test that data directory is created for SQLite databases"""
        mock_echo = mocker.patch("click.echo")
        mock_validate = mocker.patch("cli.commands.init_cmd.database_step.create_and_validate_database")
        
        options = {"add_webui_gateway": True}
        data_dir = temp_project_dir / "data"
        
        # Ensure directory doesn't exist initially
        assert not data_dir.exists()
        
        database_setup_step(temp_project_dir, options, skip_interactive=True)
        
        # Verify directory was created
        assert data_dir.exists()

    def test_orchestrator_without_agent_name_uses_default(self, temp_project_dir, mocker, mock_database_operations):
        """Test orchestrator database uses default filename when agent_name is missing"""
        mock_echo = mocker.patch("click.echo")
        mock_validate = mocker.patch("cli.commands.init_cmd.database_step.create_and_validate_database")
        
        options = {"use_orchestrator_db": True}
        
        result = database_setup_step(temp_project_dir, options, skip_interactive=True)
        
        assert result is True
        assert "orchestrator.db" in options["orchestrator_database_url"]

    def test_skip_interactive_with_no_url_uses_default_sqlite(self, temp_project_dir, mocker, mock_database_operations):
        """Test skip interactive mode without URL uses default SQLite"""
        mock_echo = mocker.patch("click.echo")
        mock_validate = mocker.patch("cli.commands.init_cmd.database_step.create_and_validate_database")
        
        options = {"add_webui_gateway": True}
        
        result = database_setup_step(temp_project_dir, options, skip_interactive=True)
        
        assert result is True
        assert "sqlite:///" in options["web_ui_gateway_database_url"]
        assert "webui_gateway.db" in options["web_ui_gateway_database_url"]