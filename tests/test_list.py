from podman_hpc_client import PodmanHpcClient


def test_list(api_service, test_uri):
    with PodmanHpcClient(base_url=test_uri) as client:
        image_name = "docker.io/library/hello-world"
        image_name_with_tag = f"{image_name}:latest"

        if image_name_with_tag in [image.tags[0] for image in client.images.list()]:
            number_of_images = len(client.images.list())
            client.images.remove(image_name, force=True)
            assert len(client.images.list()) == number_of_images - 1

        image = client.images.pull(image_name, tag="latest")
        assert image.tags == [image_name_with_tag]
        images = client.images.list()
        assert image in images
