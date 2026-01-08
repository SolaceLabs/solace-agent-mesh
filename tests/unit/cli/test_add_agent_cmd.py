import os
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from cli.main import cli


@pytest.fixture
def project_dir(tmp_path):
    """Create a temporary project directory for testing"""
    project_path = tmp_path / "test_project"
    project_path.mkdir()
    # Store the original CWD and change to the new project directory
    original_cwd = Path.cwd()
    os.chdir(project_path)
    # A basic init is needed for add-agent to work
    runner = CliRunner()
    runner.invoke(
        cli,
        ["init", "--skip", "--agent-name", "MyOrchestrator"],
        catch_exceptions=False,
    )
    yield project_path
    # Restore the original CWD and clean up the temp directory
    os.chdir(original_cwd)
    shutil.rmtree(project_path)


def test_add_agent_default_db_generation(project_dir):
    """
    Test that the 'add agent' command generates a default SQLite database
    for a new agent when the session service type is 'sql'.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "add",
            "agent",
            "newAgent",
            "--session-service-type",
            "sql",
            "--namespace",
            "test",
            "--supports-streaming",
            "y",
            "--model-type",
            "general",
            "--instruction",
            "Test instruction",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"CLI command failed: {result.output}"
    agent_config_path = project_dir / "configs" / "agents" / "new_agent_agent.yaml"
    assert agent_config_path.exists(), "Agent config file was not created."
    with open(agent_config_path) as f:
        content = f.read()
        assert 'database_url: "${NEW_AGENT_DATABASE_URL, sqlite:///new_agent.db}"' in content


@pytest.mark.xfail(reason="This test needs to be reviewed and fixed.")
def test_add_agent_custom_db_url(project_dir, mocker):
    """
    Test that 'add agent' uses the provided --database-url and does not
    attempt a real connection.
    """
    mocker.patch("cli.commands.add_cmd.agent_cmd.create_engine")
    runner = CliRunner()
    custom_db_url = "postgresql://user:pass@host/customdb"
    result = runner.invoke(
        cli,
        [
            "add",
            "agent",
            "dbAgent",
            "--session-service-type",
            "sql",
            "--database-url",
            custom_db_url,
            "--namespace",
            "test",
            "--supports-streaming",
            "y",
            "--model-type",
            "general",
            "--instruction",
            "Test instruction",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"CLI command failed: {result.output}"
    assert not (project_dir / "data" / "db_agent.db").exists(), (
        "Default agent database should not have been created."
    )
    agent_config_path = project_dir / "configs" / "agents" / "db_agent_agent.yaml"
    assert agent_config_path.exists(), "Agent config file was not created."
    with open(agent_config_path) as f:
        content = f.read()
        env_file = project_dir / ".env"
        assert env_file.exists(), ".env file was not created."
        with open(env_file) as f:
            env_content = f.read()
            assert f'DB_AGENT_DATABASE_URL="{custom_db_url}"' in env_content
        assert 'database_url: "${DB_AGENT_DATABASE_URL}"' in content


@pytest.mark.xfail(reason="This test needs to be reviewed and fixed.")
def test_add_agent_db_validation_failure(project_dir, mocker):
    """
    Test that 'add agent' fails if the database URL validation fails.
    """
    mocker.patch(
        "cli.commands.add_cmd.agent_cmd.create_engine",
        side_effect=Exception("Test DB connection error"),
    )
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "add",
            "agent",
            "failAgent",
            "--session-service-type",
            "sql",
            "--database-url",
            "bad-protocol://foo",
            "--namespace",
            "test",
            "--supports-streaming",
            "y",
            "--model-type",
            "general",
            "--instruction",
            "Test instruction",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 1, "CLI command should have failed."
    assert "Error validating database URL" in result.output
    assert "Test DB connection error" in result.output
    assert not (
        project_dir / "configs" / "agents" / "fail_agent_agent.yaml"
    ).exists(), "Agent config file should not have been created on failure."
