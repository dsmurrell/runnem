import os
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from runnem.cli import main as cli_main
from runnem.core import (
    SCREEN_PREFIX,
    init_project,
)


@pytest.fixture
def mock_screen_sessions():
    """Mock screen session management."""
    _sessions = []

    def _mock_sessions():
        return _sessions

    def _add_session(project_name: str, service_name: str):
        # Format: "8261.runnem-project_a-service1\t(Detached)"
        session = f"8261.{SCREEN_PREFIX}-{project_name}-{service_name}\t(Detached)"
        _sessions.append(session)

    def _clear_sessions():
        _sessions.clear()

    return _mock_sessions, _add_session, _clear_sessions


@pytest.fixture
def mock_subprocess_run():
    """Mock subprocess.run to simulate screen commands."""

    def _mock_run(*args, **kwargs):
        command = kwargs.get("shell", False) and kwargs.get("capture_output", False)
        if command and "screen -ls" in str(args):
            # Return a mock screen list result
            mock_result = MagicMock()
            mock_result.stdout = "\n".join(_mock_run.sessions)
            return mock_result
        return MagicMock()

    _mock_run.sessions = []
    return _mock_run


@pytest.fixture
def project_a_config():
    """Return configuration for project A."""
    return {
        "project_name": "project_a",
        "services": {
            "service1": {
                "command": "echo 'service1'",
                "url": "http://localhost:8001",
            },
            "service2": {
                "command": "echo 'service2'",
                "url": "http://localhost:8002",
                "depends_on": ["service1"],
            },
        },
    }


@pytest.fixture
def project_b_config():
    """Return configuration for project B."""
    return {
        "project_name": "project_b",
        "services": {
            "service3": {
                "command": "echo 'service3'",
                "url": "http://localhost:8003",
            },
            "service4": {
                "command": "echo 'service4'",
                "url": "http://localhost:8004",
                "depends_on": ["service3"],
            },
        },
    }


@pytest.fixture
def setup_projects(project_a_config, project_b_config):
    """Set up two projects in temporary directories."""
    with CliRunner().isolated_filesystem():
        # Create project A
        os.makedirs("project_a", exist_ok=True)
        os.chdir("project_a")
        init_project("project_a")
        project_a_dir = os.getcwd()
        os.chdir("..")

        # Create project B
        os.makedirs("project_b", exist_ok=True)
        os.chdir("project_b")
        init_project("project_b")
        project_b_dir = os.getcwd()
        os.chdir("..")

        yield project_a_dir, project_b_dir


def test_project_switching_scenario(
    setup_projects,
    project_a_config,
    project_b_config,
    mock_screen_sessions,
    mock_subprocess_run,
):
    """Test the complete project switching scenario."""
    project_a_dir, project_b_dir = setup_projects
    mock_sessions, add_session, clear_sessions = mock_screen_sessions
    runner = CliRunner()

    # Mock screen session management
    with patch("runnem.core.subprocess.run", side_effect=mock_subprocess_run), patch("runnem.core.get_running_screen_sessions", side_effect=mock_sessions):
        # Start project A
        os.chdir(project_a_dir)
        result = runner.invoke(cli_main, ["up"], input="y\n")
        assert result.exit_code == 0
        assert "Checking ports" in result.output

        # Simulate project A services running
        add_session("project_a", "service1")
        add_session("project_a", "service2")
        mock_subprocess_run.sessions = mock_sessions()

        # Try to start project B while A is running
        os.chdir(project_b_dir)
        result = runner.invoke(cli_main, ["up"], input="y\n")
        assert result.exit_code == 1
        assert "Found running services from other projects" in result.output
        assert "You must stop all services from other projects" in result.output

        # Stop project A
        os.chdir(project_a_dir)
        result = runner.invoke(cli_main, ["down"], input="y\n")
        assert result.exit_code == 0
        clear_sessions()
        mock_subprocess_run.sessions = []

        # Now start project B
        os.chdir(project_b_dir)
        result = runner.invoke(cli_main, ["up"], input="y\n")
        assert result.exit_code == 0
        assert "Checking ports" in result.output

        # Simulate project B services running
        add_session("project_b", "service3")
        add_session("project_b", "service4")
        mock_subprocess_run.sessions = mock_sessions()

        # Stop project B
        result = runner.invoke(cli_main, ["down"], input="y\n")
        assert result.exit_code == 0
        clear_sessions()
        mock_subprocess_run.sessions = []


def test_project_switching_with_ports(
    setup_projects,
    project_a_config,
    project_b_config,
    mock_screen_sessions,
    mock_subprocess_run,
):
    """Test project switching with port conflicts."""
    project_a_dir, project_b_dir = setup_projects
    mock_sessions, add_session, clear_sessions = mock_screen_sessions
    runner = CliRunner()

    # Mock screen session management
    with patch("runnem.core.subprocess.run", side_effect=mock_subprocess_run), patch("runnem.core.get_running_screen_sessions", side_effect=mock_sessions):
        # Start project A
        os.chdir(project_a_dir)
        result = runner.invoke(cli_main, ["up"], input="y\n")
        assert result.exit_code == 0
        assert "Checking ports" in result.output

        # Simulate project A services running
        add_session("project_a", "service1")
        add_session("project_a", "service2")
        mock_subprocess_run.sessions = mock_sessions()

        # Try to start project B with conflicting ports
        os.chdir(project_b_dir)
        result = runner.invoke(cli_main, ["up"], input="y\n")
        assert result.exit_code == 1
        assert "Found running services from other projects" in result.output

        # Stop project A
        os.chdir(project_a_dir)
        result = runner.invoke(cli_main, ["down"], input="y\n")
        assert result.exit_code == 0
        clear_sessions()
        mock_subprocess_run.sessions = []

        # Now start project B
        os.chdir(project_b_dir)
        result = runner.invoke(cli_main, ["up"], input="y\n")
        assert result.exit_code == 0
        assert "Checking ports" in result.output

        # Simulate project B services running
        add_session("project_b", "service3")
        add_session("project_b", "service4")
        mock_subprocess_run.sessions = mock_sessions()

        # Stop project B
        result = runner.invoke(cli_main, ["down"], input="y\n")
        assert result.exit_code == 0
        clear_sessions()
        mock_subprocess_run.sessions = []
