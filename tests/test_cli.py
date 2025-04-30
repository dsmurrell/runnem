import os
import tempfile

import pytest
from click.testing import CliRunner

from runnem.cli import main


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
