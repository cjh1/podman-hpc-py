from podman.client import (
    PodmanClient,
    ImagesManager,
    ContainersManager,
    cached_property,
)

from podman_hpc.podman_hpc import SiteConfig

from .containers import PodmanHpcContainersManager
from .images import PodmanHpcImagesManager


class PodmanHpcClient(PodmanClient):
    def __init__(self, squash_dir=None, log_level=None, **kwargs):
        self._site_config = SiteConfig(squash_dir=squash_dir, log_level=log_level)

        super().__init__(**kwargs)

    @cached_property
    def images(self) -> ImagesManager:
        """Returns Manager for operations on images stored by a Podman service."""
        return PodmanHpcImagesManager(self._site_config, client=self.api)

    @cached_property
    def containers(self) -> ContainersManager:
        """Returns Manager for operations on containers managed by a Podman service."""
        return PodmanHpcContainersManager(self._site_config, client=self.api)
