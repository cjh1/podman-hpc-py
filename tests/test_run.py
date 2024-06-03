import os

from podman_hpc_client import PodmanHpcClient
from podman.errors.exceptions import ContainerError


def test_run(api_service, test_uri):
    with PodmanHpcClient(base_url=test_uri) as client:
        expected = "Hello, World!"
        command = ["echo", expected]
        image = client.images.pull("docker.io/library/alpine", tag="latest")
        assert image.tags == ["docker.io/library/alpine:latest"]

        log_config = {
            "Type": "json-file",
        }

        output = client.containers.run(
            image.id,
            command=command,
            stdout=True,
            stderr=True,
            log_config=log_config,
            remove=True,
        )

    assert output.decode("utf-8").strip() == expected


def test_run_gpu(api_service, test_uri):
    with PodmanHpcClient(base_url=test_uri) as client:
        command = ["nvidia-smi", "--list-gpus"]
        repository = "docker.io/nvidia/cuda"
        tag = "12.2.2-devel-ubi8"
        image = client.images.pull(repository, tag=tag)
        assert image.tags == [f"{repository}:{tag}"]

        log_config = {
            "Type": "json-file",
        }

        # First type without --gpus
        try:
            output = client.containers.run(
                image.id,
                command=command,
                stdout=True,
                stderr=True,
                log_config=log_config,
                remove=True,
            )

            assert False, "Expected ContainerError"
        except ContainerError:
            pass

            output = client.containers.run(
                image.id,
                command=command,
                stdout=True,
                stderr=True,
                log_config=log_config,
                remove=True,
                gpu=True,
            )

        # assert that we have at least one GPU
        assert "GPU 0" in output.decode("utf-8")


def test_run_host_env(api_service, test_uri):
    with PodmanHpcClient(base_url=test_uri) as client:
        command = ["echo", "$USER"]
        repository = "docker.io/library/alpine"
        tag = "latest"
        image = client.images.pull(repository, tag=tag)
        assert image.tags == [f"{repository}:{tag}"]

        # Check that the host value of NVIDIA_VISIBLE_DEVICES is
        # set on the container
        os.environ["NVIDIA_VISIBLE_DEVICES"] = "all"

        container = None
        try:
            container = client.containers.create(image.id, command=command, gpu=True)

            info = container.inspect()
            env = info["Config"]["Env"]
            assert "NVIDIA_VISIBLE_DEVICES=all" in env

        finally:
            if container:
                container.remove()


def test_run_host_env_prefix(api_service, test_uri):
    with PodmanHpcClient(base_url=test_uri) as client:
        command = ["echo", "$USER"]
        repository = "docker.io/library/alpine"
        tag = "latest"
        image = client.images.pull(repository, tag=tag)
        assert image.tags == [f"{repository}:{tag}"]

        # Check that host environment variable prefix with SLURM_*
        # are added to the container
        name = "SLURM_HELLO"
        value = "World!"
        os.environ[name] = value

        container = None
        try:
            container = client.containers.create(image.id, command=command, mpi=True)

            info = container.inspect()
            env = info["Config"]["Env"]
            assert f"{name}={value}" in env

        finally:
            if container:
                container.remove()
