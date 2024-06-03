from typing import List, Union, Iterator, Optional


from podman.client import (
    ImagesManager,
)
from podman.domain.images import Image

from podman_hpc.migrate2scratch import MigrateUtils


class PodmanHpcImagesManager(ImagesManager):
    def __init__(self, site_config, **kwargs):
        self._site_config = site_config

        super().__init__(**kwargs)

    def pull(
        self,
        repository: str,
        tag: Optional[str] = None,
        all_tags: bool = False,
        **kwargs,
    ) -> Union[Image, List[Image], Iterator[str]]:
        images = super().pull(repository, tag, all_tags, **kwargs)

        # Now migrate the images
        for image in images if isinstance(images, list) else [images]:
            mu = MigrateUtils(conf=self._site_config)
            tags = image.tags

            if not tags:
                raise RuntimeError(f"Pull failed for Image: {repository}/{tag} ")

            mu.migrate_image(tags[0])

        return images
