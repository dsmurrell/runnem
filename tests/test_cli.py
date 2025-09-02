import os
import tempfile
import time
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from runnem.cli import main
from runnem.core import is_service_running, stop_all_running_services


@pytest.fixture
def temp_project_dir():
    """Create a temporary directory for testing project initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        original_dir = os.getcwd()
        os.chdir(tmpdir)
        yield tmpdir
        os.chdir(original_dir)


@pytest.fixture
def cli_runner():
    """Create a Click CLI runner."""
    return CliRunner()


def test_cli_init(temp_project_dir, cli_runner):
    """Test the init command."""
    result = cli_runner.invoke(main, ["init", "test_project"])
    assert result.exit_code == 0
    assert "Initialized project test_project" in result.output

    # Verify config file was created
    config_path = os.path.join(temp_project_dir, "runnem.yaml")
    assert os.path.exists(config_path)


def test_cli_up_no_project(cli_runner):
    """Test the up command without a project."""
    result = cli_runner.invoke(main, ["up"])
    assert result.exit_code == 0
    assert "No project found" in result.output


def test_cli_down_no_project(cli_runner):
    """Test the down command without a project."""
    result = cli_runner.invoke(main, ["down"])
    assert result.exit_code == 0
    assert "No services running" in result.output


def test_cli_restart_no_project(cli_runner):
    """Test the restart command without a project."""
    result = cli_runner.invoke(main, ["restart"])
    assert result.exit_code == 0
    assert "No project found" in result.output


def test_cli_restart_with_service(temp_project_dir, cli_runner):
    """Test the restart command with an actual running service."""
    # Create a config with a long-running service
    config = {
        "project_name": "test_restart_project",
        "services": {
            "long_service": {
                "command": "sleep 30",  # Long enough to test restart
                "url": "http://localhost:8081",
            }
        },
    }

    # Write config file
    config_path = Path(temp_project_dir) / "runnem.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)

    try:
        # Start the service
        result = cli_runner.invoke(main, ["up", "long_service"])
        assert result.exit_code == 0

        # Give it a moment to start
        time.sleep(1)

        # Verify service is running
        assert is_service_running("test_restart_project", "long_service")

        # Restart the service
        result = cli_runner.invoke(main, ["restart", "long_service"])
        assert result.exit_code == 0
        assert "Restarting services" in result.output

        # Give it a moment to restart
        time.sleep(1)

        # Verify service is still running after restart
        assert is_service_running("test_restart_project", "long_service")

    finally:
        # Clean up - stop all services
        stop_all_running_services()


def test_cli_restart_stopped_service(temp_project_dir, cli_runner):
    """Test the restart command on a stopped service (should start it)."""
    # Create a config with a long-running service
    config = {
        "project_name": "test_restart_stopped_project",
        "services": {
            "stopped_service": {
                "command": "sleep 30",  # Long enough to test restart
                "url": "http://localhost:8082",
            }
        },
    }

    # Write config file
    config_path = Path(temp_project_dir) / "runnem.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)

    try:
        # Verify service is not running initially
        assert not is_service_running("test_restart_stopped_project", "stopped_service")

        # Restart the stopped service (should start it)
        result = cli_runner.invoke(main, ["restart", "stopped_service"])
        assert result.exit_code == 0
        assert "Restarting services" in result.output

        # Give it a moment to start
        time.sleep(1)

        # Verify service is now running
        assert is_service_running("test_restart_stopped_project", "stopped_service")

    finally:
        # Clean up - stop all services
        stop_all_running_services()


def test_cli_run_command(temp_project_dir, cli_runner):
    """Test the run command (up + log)."""
    # Clean up any existing services first to avoid conflicts
    stop_all_running_services()

    # Create a config with a service
    config = {
        "project_name": "test_run_project",
        "services": {
            "test_service": {
                "command": "echo 'Hello from test service'",
                "url": "http://localhost:8083",
            },
        },
    }

    # Write config file
    config_path = Path(temp_project_dir) / "runnem.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)

    try:
        # Test run command - this should start the service and then try to view logs
        # Since the service will exit quickly (echo command), we expect it to start
        # but the log viewing might not find a running screen session
        result = cli_runner.invoke(main, ["run", "test_service"])
        # The command should complete successfully even if log viewing fails
        assert result.exit_code == 0
        # Should contain evidence that it tried to start the service
        assert "Starting test_service" in result.output

    finally:
        # Clean up - stop all services
        stop_all_running_services()


def test_cli_rerun_command(temp_project_dir, cli_runner):
    """Test the rerun command (restart + log)."""
    # Clean up any existing services first to avoid conflicts
    stop_all_running_services()

    # Create a config with a service
    config = {
        "project_name": "test_rerun_project",
        "services": {
            "test_service": {
                "command": "echo 'Hello from rerun test'",  # Quick command for testing
                "url": "http://localhost:8084",
            },
        },
    }

    # Write config file
    config_path = Path(temp_project_dir) / "runnem.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)

    try:
        # Test rerun command - this should restart the service and then try to view logs
        result = cli_runner.invoke(main, ["rerun", "test_service"])
        assert result.exit_code == 0
        assert "Restarting service" in result.output

    finally:
        # Clean up - stop all services
        stop_all_running_services()


def test_cli_run_no_project(cli_runner):
    """Test the run command when no project is found."""
    result = cli_runner.invoke(main, ["run", "test_service"])
    assert result.exit_code == 0
    assert "No project found" in result.output


def test_cli_rerun_no_project(cli_runner):
    """Test the rerun command when no project is found."""
    result = cli_runner.invoke(main, ["rerun", "test_service"])
    assert result.exit_code == 0
    assert "No project found" in result.output


def test_cli_run_unknown_service(temp_project_dir, cli_runner):
    """Test the run command with an unknown service."""
    # Create a config with no services
    config = {
        "project_name": "test_run_unknown_project",
        "services": {},
    }

    # Write config file
    config_path = Path(temp_project_dir) / "runnem.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)

    # Test run command with unknown service
    result = cli_runner.invoke(main, ["run", "unknown_service"])
    assert result.exit_code == 0
    assert "Unknown service: unknown_service" in result.output


def test_cli_rerun_unknown_service(temp_project_dir, cli_runner):
    """Test the rerun command with an unknown service."""
    # Create a config with no services
    config = {
        "project_name": "test_rerun_unknown_project",
        "services": {},
    }

    # Write config file
    config_path = Path(temp_project_dir) / "runnem.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)

    # Test rerun command with unknown service
    result = cli_runner.invoke(main, ["rerun", "unknown_service"])
    assert result.exit_code == 0
    assert "Unknown service: unknown_service" in result.output


def test_cli_list_no_project(cli_runner):
    """Test the list command without a project."""
    result = cli_runner.invoke(main, ["list"])
    assert result.exit_code == 0
    assert "No project found" in result.output


def test_cli_log_no_project(cli_runner):
    """Test the log command without a project."""
    result = cli_runner.invoke(main, ["log", "test_service"])
    assert result.exit_code == 0
    assert "No project found" in result.output


def test_cli_kill_port(cli_runner):
    """Test the kill command for a port."""
    # Test with a port that's likely not in use
    result = cli_runner.invoke(main, ["kill", "8080"])
    assert result.exit_code == 0
    assert "No process found on port 8080" in result.output


def test_cli_help(cli_runner):
    """Test the help command."""
    result = cli_runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "A service manager for managing multiple services in a project" in result.output
