import pytest

from runnem.core import (
    build_dependency_graph,
    check_port_conflict,
    get_project_config,
    get_service_port,
    kill_port_process,
    start_service,
    stop_service,
    wait_for_service,
)


@pytest.fixture
def invalid_config():
    """Return an invalid configuration."""
    return {
        "project_name": "test_project",
        "services": {
            "invalid_service": {
                "command": "nonexistent-command",
                "url": "http://localhost:9999",
            },
            "missing_command": {"url": "http://localhost:8888"},
            "invalid_dependency": {
                "command": "echo 'test'",
                "url": "http://localhost:7777",
                "depends_on": ["nonexistent_service"],
            },
        },
    }


def test_start_nonexistent_service(invalid_config):
    """Test starting a service that doesn't exist."""
    # The function prints an error message instead of raising KeyError
    start_service("nonexistent_service", invalid_config)
    # Test passes if we reach here without exception


def test_stop_nonexistent_service(invalid_config):
    """Test stopping a service that doesn't exist."""
    # Should not raise an exception, just print a warning
    stop_service("nonexistent_service", invalid_config)


def test_service_missing_command(invalid_config):
    """Test starting a service with missing command."""
    with pytest.raises(KeyError) as exc_info:
        start_service("missing_command", invalid_config)
    assert str(exc_info.value) == "'command'"


def test_invalid_dependency(invalid_config):
    """Test handling invalid service dependencies."""
    graph = build_dependency_graph(invalid_config)
    assert "nonexistent_service" not in graph
    assert "invalid_dependency" in graph
    assert graph["invalid_dependency"] == ["nonexistent_service"]


def test_invalid_port():
    """Test handling invalid port numbers."""
    # Test with invalid port numbers
    assert not check_port_conflict(-1)
    # Port 0 is actually valid in some cases, so we'll skip it
    assert not check_port_conflict(65536)


def test_kill_invalid_port():
    """Test killing process on invalid port."""
    # Should return False for invalid ports
    assert not kill_port_process(-1)
    # Port 0 is actually valid in some cases, so we'll skip it
    assert not kill_port_process(65536)


def test_get_service_port_invalid_url():
    """Test getting port from invalid URLs."""
    config = {
        "services": {
            "test": {"command": "echo 'test'", "url": "not-a-valid-url"},
            "test2": {"command": "echo 'test'", "url": "http://localhost:invalid"},
            "test3": {"command": "echo 'test'", "url": "http://localhost:"},
        }
    }

    # Should return None for invalid URLs
    assert get_service_port("test", config) is None
    assert get_service_port("test2", config) is None
    assert get_service_port("test3", config) is None


def test_wait_for_service_timeout():
    """Test service wait timeout."""
    config = {
        "services": {
            "test": {
                "command": "echo 'test'",
                "url": "http://localhost:9999",  # Unlikely to be running
            }
        }
    }

    # Should return False after timeout
    assert not wait_for_service("test", config)


def test_wait_for_service_invalid_url():
    """Test waiting for service with invalid URL."""
    config = {
        "services": {"test": {"command": "echo 'test'", "url": "not-a-valid-url"}}
    }

    # Should return False for invalid URL
    assert not wait_for_service("test", config)


def test_project_config_not_found():
    """Test handling missing project configuration."""
    with pytest.raises(FileNotFoundError):
        get_project_config("nonexistent_project")
