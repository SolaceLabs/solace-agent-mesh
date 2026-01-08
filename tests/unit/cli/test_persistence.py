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
    original_cwd = Path.cwd()
    os.chdir(project_path)
    runner = CliRunner()
    runner.invoke(
        cli,
        ["init", "--skip", "--agent-name", "MyOrchestrator"],
        catch_exceptions=False,
    )
    yield project_path
    os.chdir(original_cwd)
    shutil.rmtree(project_path)


def test_add_agent_idempotency(project_dir):
    """
    Test that running 'add agent' multiple times for the same agent updates the config correctly.
    """
    runner = CliRunner()
    # First run
    result1 = runner.invoke(
        cli,
        [
            "add",
            "agent",
            "idempotentAgent",
            "--session-service-type",
            "sql",
            "--instruction",
            "First instruction",
            "--skip",
        ],
        catch_exceptions=False,
    )
    assert result1.exit_code == 0, f"First run failed: {result1.output}"
    agent_config_path = (
        project_dir / "configs" / "agents" / "idempotent_agent_agent.yaml"
    )
    with open(agent_config_path) as f:
        content1 = f.read()
    assert "First instruction" in content1

    # Second run with different instruction
    result2 = runner.invoke(
        cli,
        [
            "add",
            "agent",
            "idempotentAgent",
            "--session-service-type",
            "sql",
            "--instruction",
            "Second instruction",
            "--skip",
        ],
        catch_exceptions=False,
    )
    assert result2.exit_code == 0, f"Second run failed: {result2.output}"
    with open(agent_config_path) as f:
        content2 = f.read()
    assert "Second instruction" in content2
    assert "First instruction" not in content2
