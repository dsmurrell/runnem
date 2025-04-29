import os
import tempfile
from pathlib import Path

import pytest
import yaml


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
            "test_service": {"command": "echo 'test'", "url": "http://localhost:8080"},
            "dependent_service": {
                "command": "echo 'dependent'",
                "url": "http://localhost:8081",
                "depends_on": ["test_service"],
            },
        },
    }


@pytest.fixture
def project_with_config(temp_project_dir, sample_config):
    """Create a project with a configuration file."""
    config_path = Path(temp_project_dir) / "runnem.yaml"
    with open(config_path, "w") as f:
        yaml.dump(sample_config, f)
    return temp_project_dir
