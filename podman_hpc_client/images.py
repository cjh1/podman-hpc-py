from typing import List, Union, Iterator, Optional
import os

from podman.client import (
    ImagesManager,
)
from podman.domain.images import Image

from podman_hpc.migrate2scratch import MigrateUtils, ImageStore


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
            mu._lazy_init()  # sets mu.src_dir / mu.dst_dir

            # Ensure graph_root metadata exists
            store = ImageStore(mu.src_dir, read_only=False)
            if not (
                os.path.exists(store.layers_json) and os.path.exists(store.images_json)
            ):
                store.init_storage()
            tags = image.tags

            if not tags:
                raise RuntimeError(f"Pull failed for Image: {repository}/{tag} ")

            mu.migrate_image(tags[0])

        return images
