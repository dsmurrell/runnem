import os
import tempfile
from pathlib import Path

import pytest
import yaml

from runnem.core import (
    check_port_conflict,
    get_project_config,
    get_project_name,
    init_project,
    kill_port_process,
    list_all_services,
    start_service,
    stop_service,
)


@pytest.fixture
def temp_project_dir():
    """Create a temporary directory for testing project initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        original_dir = os.getcwd()
        os.chdir(tmpdir)
        yield tmpdir
        os.chdir(original_dir)


@pytest.fixture
def sample_config():
    """Return a sample configuration for testing."""
    return {
        "project_name": "test_project",
        "services": {
            "test_service": {"command": "echo 'test'", "url": "http://localhost:8080"}
        },
    }


def test_init_project(temp_project_dir):
    """Test project initialization."""
    project_name = "test_project"
    init_project(project_name)

    config_path = Path(temp_project_dir) / "runnem.yaml"
    assert config_path.exists()

    with open(config_path) as f:
        config = yaml.safe_load(f)
        assert config["project_name"] == project_name
        assert "services" in config


def test_get_project_name(temp_project_dir, sample_config):
    """Test getting project name from config."""
    # Create a config file
    config_path = Path(temp_project_dir) / "runnem.yaml"
    with open(config_path, "w") as f:
        yaml.dump(sample_config, f)

    project_name = get_project_name()
    assert project_name == "test_project"


def test_get_project_config(temp_project_dir, sample_config):
    """Test getting project configuration."""
    # Create a config file
    config_path = Path(temp_project_dir) / "runnem.yaml"
    with open(config_path, "w") as f:
        yaml.dump(sample_config, f)

    config = get_project_config("test_project")
    assert config["project_name"] == "test_project"
    assert "test_service" in config["services"]


def test_port_conflict_detection():
    """Test port conflict detection."""
    # This test assumes port 8080 is not in use
    assert not check_port_conflict(8080)


def test_kill_port_process():
    """Test killing process on port."""
    # This test assumes port 8080 is not in use
    assert not kill_port_process(8080)  # Should return False when no process is found


def test_service_lifecycle(temp_project_dir, sample_config):
    """Test starting and stopping a service."""
    # Create a config file
    config_path = Path(temp_project_dir) / "runnem.yaml"
    with open(config_path, "w") as f:
        yaml.dump(sample_config, f)

    # Test starting service
    start_service("test_service", sample_config)

    # Test listing services
    list_all_services(sample_config)

    # Test stopping service
    stop_service("test_service", sample_config)
