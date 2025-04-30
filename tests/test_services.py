import pytest
from unittest.mock import MagicMock, patch

from runnem.core import (
    SCREEN_PREFIX,
    build_dependency_graph,
    check_port_conflict,
    detect_cycles,
    get_service_port,
    kill_port_process,
    start_service,
    stop_service,
    topological_sort,
    wait_for_service,
)


@pytest.fixture
def complex_config():
    """Return a configuration with multiple services and dependencies."""
    return {
        "project_name": "test_project",
        "services": {
            "database": {
                "command": "echo 'database'",
                "url": "postgresql://localhost:5432",
            },
            "api": {
                "command": "echo 'api'",
                "url": "http://localhost:8000",
                "depends_on": ["database"],
            },
            "frontend": {
                "command": "echo 'frontend'",
                "url": "http://localhost:3000",
                "depends_on": ["api"],
            },
            "cache": {"command": "echo 'cache'", "url": "redis://localhost:6379"},
        },
    }


@pytest.fixture
def cyclic_config():
    """Return a configuration with cyclic dependencies."""
    return {
        "project_name": "test_project",
        "services": {
            "service1": {
                "command": "echo 'service1'",
                "url": "http://localhost:8001",
                "depends_on": ["service2"],
            },
            "service2": {
                "command": "echo 'service2'",
                "url": "http://localhost:8002",
                "depends_on": ["service3"],
            },
            "service3": {
                "command": "echo 'service3'",
                "url": "http://localhost:8003",
                "depends_on": ["service1"],
            },
        },
    }


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


def test_build_dependency_graph(complex_config):
    """Test building the dependency graph."""
    graph = build_dependency_graph(complex_config)
    assert "database" in graph
    assert "api" in graph
    assert "frontend" in graph
    assert graph["api"] == ["database"]
    assert graph["frontend"] == ["api"]
    assert graph["database"] == []
    assert graph["cache"] == []


def test_detect_cycles_no_cycle(complex_config):
    """Test cycle detection with no cycles."""
    graph = build_dependency_graph(complex_config)
    cycle = detect_cycles(graph)
    assert cycle is None


def test_detect_cycles_with_cycle(cyclic_config):
    """Test cycle detection with cycles."""
    graph = build_dependency_graph(cyclic_config)
    cycle = detect_cycles(graph)
    assert cycle is not None
    assert len(cycle) > 0
    # The cycle should contain all three services
    assert all(service in cycle for service in ["service1", "service2", "service3"])


def test_topological_sort(complex_config):
    """Test topological sorting of services."""
    graph = build_dependency_graph(complex_config)
    order = topological_sort(graph)

    # Check that dependencies come before their dependent services
    if "api" in order and "frontend" in order:
        api_idx = order.index("api")
        frontend_idx = order.index("frontend")
        assert api_idx < frontend_idx  # api should come before frontend

    if "database" in order and "api" in order:
        database_idx = order.index("database")
        api_idx = order.index("api")
        assert database_idx < api_idx  # database should come before api

    # Independent services can be in any order
    assert "cache" in order


def test_get_service_port():
    """Test extracting port from service URL."""
    service_config = {"command": "echo 'test'", "url": "http://localhost:8080"}
    config = {"services": {"test": service_config}}

    port = get_service_port("test", config)
    assert port == 8080


def test_get_service_port_https():
    """Test extracting port from HTTPS URL."""
    service_config = {"command": "echo 'test'", "url": "https://localhost:8443"}
    config = {"services": {"test": service_config}}

    port = get_service_port("test", config)
    assert port == 8443


def test_get_service_port_no_url():
    """Test handling service with no URL."""
    service_config = {"command": "echo 'test'"}
    config = {"services": {"test": service_config}}

    port = get_service_port("test", config)
    assert port is None


def test_service_url_validation():
    """Test service URL validation."""
    service_config = {"command": "echo 'test'", "url": "http://localhost:8080"}
    config = {"services": {"test": service_config}}

    # This should not raise any exceptions
    wait_for_service("test", config)


def test_service_url_validation_invalid():
    """Test service URL validation with invalid URL."""
    service_config = {"command": "echo 'test'", "url": "not-a-valid-url"}
    config = {"services": {"test": service_config}}

    # Should handle invalid URLs gracefully
    assert not wait_for_service("test", config)


def test_service_lifecycle_with_port(complex_config):
    """Test complete service lifecycle including port handling."""
    service_name = "api"

    # Ensure port is free before starting
    port = get_service_port(service_name, complex_config)
    assert port is not None
    kill_port_process(port)
    assert not check_port_conflict(port)

    # Start service
    start_service(service_name, complex_config)

    # Stop service
    stop_service(service_name, complex_config)
    assert not check_port_conflict(port)


def test_start_already_running_service(complex_config, mock_screen_sessions, mock_subprocess_run):
    """Test that starting an already running service shows a warning."""
    mock_sessions, add_session, clear_sessions = mock_screen_sessions
    service_name = "api"
    project_name = complex_config["project_name"]

    # Mock screen session management
    with patch("runnem.core.subprocess.run", side_effect=mock_subprocess_run), patch("runnem.core.get_running_screen_sessions", side_effect=mock_sessions), patch("runnem.core.print") as mock_print:
        # Simulate service already running
        add_session(project_name, service_name)
        mock_subprocess_run.sessions = mock_sessions()

        # Try to start the service again
        start_service(service_name, complex_config)

        # Verify warning was printed
        mock_print.assert_any_call(f"⚠️ {service_name} is already running in project '{project_name}'.")

        # Clean up
        clear_sessions()
        mock_subprocess_run.sessions = []
