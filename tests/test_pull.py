from podman_hpc_client import PodmanHpcClient


def test_pull(api_service, test_uri):
    with PodmanHpcClient(base_url=test_uri) as client:
        image = client.images.pull("docker.io/library/alpine", tag="latest")
        assert image.tags == ["docker.io/library/alpine:latest"]
