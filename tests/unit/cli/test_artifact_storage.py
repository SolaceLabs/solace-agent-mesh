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


def test_add_agent_filesystem_artifact_service(project_dir):
    """
    Test that the 'add agent' command correctly configures filesystem artifact service.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "add",
            "agent",
            "testAgent",
            "--artifact-service-type",
            "filesystem",
            "--artifact-service-base-path",
            "/custom/path",
            "--artifact-service-scope",
            "app",
            "--session-service-type",
            "memory",
            "--namespace",
            "test",
            "--supports-streaming",
            "y",
            "--model-type",
            "general",
            "--instruction",
            "Test instruction",
            "--skip",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, f"CLI command failed: {result.output}"

    agent_config_path = project_dir / "configs" / "agents" / "test_agent_agent.yaml"
    assert agent_config_path.exists(), "Agent config file was not created."

    with open(agent_config_path) as f:
        content = f.read()
        # Check that filesystem artifact service is configured
        assert 'type: "filesystem"' in content
        assert 'base_path: "/custom/path"' in content
        assert "artifact_scope: app" in content


@pytest.mark.xfail(reason="This test needs to be reviewed and fixed.")
def test_add_agent_s3_artifact_service_minimal(project_dir):
    """
    Test that the 'add agent' command correctly configures S3 artifact service with minimal configuration.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "add",
            "agent",
            "s3Agent",
            "--artifact-service-type",
            "s3",
            "--artifact-service-bucket-name",
            "my-test-bucket",
            "--artifact-service-scope",
            "namespace",
            "--session-service-type",
            "memory",
            "--namespace",
            "test",
            "--supports-streaming",
            "y",
            "--model-type",
            "general",
            "--instruction",
            "Test instruction",
            "--skip",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, f"CLI command failed: {result.output}"

    agent_config_path = project_dir / "configs" / "agents" / "s3_agent_agent.yaml"
    assert agent_config_path.exists(), "Agent config file was not created."

    with open(agent_config_path) as f:
        content = f.read()
        # Check that S3 artifact service is configured
        assert 'type: "s3"' in content
        assert 'bucket_name: "my-test-bucket"' in content
        assert "artifact_scope: namespace" in content
        # Region should be included by default
        assert 'region: "us-east-1"' in content
        # Endpoint URL should not be present if not specified
        assert "endpoint_url:" not in content


@pytest.mark.xfail(reason="This test needs to be reviewed and fixed.")
def test_add_agent_s3_artifact_service_full_config(project_dir):
    """
    Test that the 'add agent' command correctly configures S3 artifact service with full configuration.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "add",
            "agent",
            "s3FullAgent",
            "--artifact-service-type",
            "s3",
            "--artifact-service-bucket-name",
            "my-full-bucket",
            "--artifact-service-endpoint-url",
            "https://s3.custom-domain.com",
            "--artifact-service-region",
            "eu-west-1",
            "--artifact-service-scope",
            "custom",
            "--session-service-type",
            "memory",
            "--namespace",
            "test",
            "--supports-streaming",
            "y",
            "--model-type",
            "general",
            "--instruction",
            "Test instruction",
            "--skip",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, f"CLI command failed: {result.output}"

    agent_config_path = project_dir / "configs" / "agents" / "s3_full_agent_agent.yaml"
    assert agent_config_path.exists(), "Agent config file was not created."

    with open(agent_config_path) as f:
        content = f.read()
        # Check that S3 artifact service is configured with all options
        assert 'type: "s3"' in content
        assert 'bucket_name: "my-full-bucket"' in content
        assert 'endpoint_url: "https://s3.custom-domain.com"' in content
        assert 'region: "eu-west-1"' in content
        assert "artifact_scope: custom" in content


def test_add_agent_memory_artifact_service(project_dir):
    """
    Test that the 'add agent' command correctly configures memory artifact service.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "add",
            "agent",
            "memoryAgent",
            "--artifact-service-type",
            "memory",
            "--artifact-service-scope",
            "app",
            "--session-service-type",
            "memory",
            "--namespace",
            "test",
            "--supports-streaming",
            "y",
            "--model-type",
            "general",
            "--instruction",
            "Test instruction",
            "--skip",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, f"CLI command failed: {result.output}"

    agent_config_path = project_dir / "configs" / "agents" / "memory_agent_agent.yaml"
    assert agent_config_path.exists(), "Agent config file was not created."

    with open(agent_config_path) as f:
        content = f.read()
        # Check that memory artifact service is configured
        assert 'type: "memory"' in content
        assert "artifact_scope: app" in content
        # Memory service should not have filesystem-specific configuration
        assert (
            'base_path: "/tmp/samv2"' not in content
        )  # Should not have the default filesystem path
        assert "bucket_name:" not in content


def test_add_agent_gcs_artifact_service(project_dir):
    """
    Test that the 'add agent' command correctly configures GCS artifact service.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "add",
            "agent",
            "gcsAgent",
            "--artifact-service-type",
            "gcs",
            "--artifact-service-scope",
            "namespace",
            "--session-service-type",
            "memory",
            "--namespace",
            "test",
            "--supports-streaming",
            "y",
            "--model-type",
            "general",
            "--instruction",
            "Test instruction",
            "--skip",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, f"CLI command failed: {result.output}"

    agent_config_path = project_dir / "configs" / "agents" / "gcs_agent_agent.yaml"
    assert agent_config_path.exists(), "Agent config file was not created."

    with open(agent_config_path) as f:
        content = f.read()
        # Check that GCS artifact service is configured
        assert 'type: "gcs"' in content
        assert "artifact_scope: namespace" in content


def test_add_agent_default_shared_artifact_service(project_dir):
    """
    Test that the 'add agent' command uses default shared artifact service when not specified.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "add",
            "agent",
            "defaultAgent",
            "--session-service-type",
            "memory",
            "--namespace",
            "test",
            "--supports-streaming",
            "y",
            "--model-type",
            "general",
            "--instruction",
            "Test instruction",
            "--skip",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, f"CLI command failed: {result.output}"

    agent_config_path = project_dir / "configs" / "agents" / "default_agent_agent.yaml"
    assert agent_config_path.exists(), "Agent config file was not created."

    with open(agent_config_path) as f:
        content = f.read()
        # Check that default shared artifact service is used
        assert "*default_artifact_service" in content
        # The line should be exactly "artifact_service: *default_artifact_service"
        assert "artifact_service: *default_artifact_service" in content
        # Should not contain custom artifact service type definitions
        assert (
            'type: "memory"' not in content or content.count('type: "memory"') == 1
        )  # Only in session_service
        assert 'type: "s3"' not in content
        assert 'type: "filesystem"' not in content


def test_add_agent_artifact_service_scopes(project_dir):
    """
    Test that different artifact service scopes are correctly configured.
    """
    scopes = ["namespace", "app", "custom"]

    for scope in scopes:
        runner = CliRunner()
        agent_name = f"scope{scope.capitalize()}Agent"
        result = runner.invoke(
            cli,
            [
                "add",
                "agent",
                agent_name,
                "--artifact-service-type",
                "memory",
                "--artifact-service-scope",
                scope,
                "--session-service-type",
                "memory",
                "--namespace",
                "test",
                "--supports-streaming",
                "y",
                "--model-type",
                "general",
                "--instruction",
                "Test instruction",
                "--skip",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, (
            f"CLI command failed for scope {scope}: {result.output}"
        )

        # Convert to snake_case properly - the naming function converts to snake case and adds _agent
        from cli.utils import get_formatted_names

        formatted_names = get_formatted_names(agent_name)
        snake_case_file = formatted_names["SNAKE_CASE_NAME"]
        agent_config_path = (
            project_dir / "configs" / "agents" / f"{snake_case_file}_agent.yaml"
        )
        assert agent_config_path.exists(), (
            f"Agent config file was not created for scope {scope}. Expected: {agent_config_path}"
        )

        with open(agent_config_path) as f:
            content = f.read()
            assert f"artifact_scope: {scope}" in content


@pytest.mark.xfail(reason="This test needs to be reviewed and fixed.")
def test_add_agent_s3_with_empty_optional_params(project_dir):
    """
    Test that S3 artifact service works correctly when optional parameters are empty.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "add",
            "agent",
            "s3EmptyAgent",
            "--artifact-service-type",
            "s3",
            "--artifact-service-bucket-name",
            "my-bucket",
            "--artifact-service-scope",
            "app",
            "--session-service-type",
            "memory",
            "--namespace",
            "test",
            "--supports-streaming",
            "y",
            "--model-type",
            "general",
            "--instruction",
            "Test instruction",
            "--skip",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, f"CLI command failed: {result.output}"

    agent_config_path = project_dir / "configs" / "agents" / "s3_empty_agent_agent.yaml"
    assert agent_config_path.exists(), "Agent config file was not created."

    with open(agent_config_path) as f:
        content = f.read()
        assert 'type: "s3"' in content
        assert 'bucket_name: "my-bucket"' in content
        # When not specified, endpoint_url should not be included
        assert "endpoint_url:" not in content
        # When not specified, region should default to us-east-1
        assert 'region: "us-east-1"' in content
