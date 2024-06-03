import subprocess

import pytest
import time
from pathlib import Path


@pytest.fixture(scope="session")
def test_socket_path():
    return "/tmp/podman.sock"


@pytest.fixture(scope="session")
def test_uri(test_socket_path):
    return f"unix://{test_socket_path}"


@pytest.fixture(scope="session")
def api_service(test_socket_path, test_uri):
    command = ["podman-hpc", "system", "service", "--time", "0", test_uri]

    service = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    while not Path(test_socket_path).exists():
        time.sleep(1)

    # Check it started successfully
    assert not service.poll()
    yield service
    # Shut it down at the end of the pytest session
    service.terminate()
