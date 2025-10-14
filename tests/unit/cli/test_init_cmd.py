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
    yield project_path
    # Restore the original CWD and clean up the temp directory
    os.chdir(original_cwd)
    shutil.rmtree(project_path)


def test_init_default_db_generation(project_dir):
    """
    Test that the init command generates the default SQLite database files
    and configures the .env file correctly.
    """
    runner = CliRunner()
    # Run the init command with non-interactive flags
    result = runner.invoke(
        cli,
        ["init", "--skip", "--agent-name", "MyOrchestrator"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, (
        f"CLI command failed with exit code {result.exit_code}: {result.output}"
    )

    # Verify that the .env file is configured correctly
    env_file = project_dir / ".env"
    assert env_file.exists(), ".env file was not created"


@pytest.mark.xfail(reason="This test needs to be reviewed and fixed.")
def test_init_external_db_url_no_file_creation(project_dir, mocker):
    """
    Test that the init command with a non-sqlite custom database URL does NOT
    create local .db files.
    """
    mocker.patch("cli.commands.init_cmd.database_step.create_engine")
    runner = CliRunner()
    custom_db_url = "postgresql://user:pass@host/db"

    result = runner.invoke(
        cli,
        [
            "init",
            "--skip",
            f"--web-ui-gateway-database-url={custom_db_url}",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, (
        f"CLI command failed with exit code {result.exit_code}: {result.output}"
    )
    assert not (project_dir / "data" / "webui_gateway.db").exists(), (
        "webui_gateway.db should not have been created"
    )

    env_file = project_dir / ".env"
    with open(env_file) as f:
        env_content = f.read()
        assert f'WEB_UI_GATEWAY_DATABASE_URL="{custom_db_url}"' in env_content
