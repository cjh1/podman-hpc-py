from typing import Dict, List, Union, Generator, Iterator, Tuple, Optional
from pathlib import Path

import yaml

from podman.client import (
    PodmanClient,
    ImagesManager,
    ContainersManager,
    cached_property,
)
from podman.domain.images import Image
from podman.domain.containers import Container

from podman_hpc.podman_hpc import SiteConfig
from podman_hpc import siteconfig as site_config_module
from podman_hpc.migrate2scratch import MigrateUtils

uri = "unix:///tmp/podman.sock"


def _add_kwargs(current_kwargs: Dict[str, str], new_kwargs: Dict[str, str]):
    for k, v in new_kwargs.items():
        if k in current_kwargs:
            if isinstance(current_kwargs[k], dict):
                current_kwargs[k].update(v)
                continue
            # Default multiple values to list
            if not isinstance(current_kwargs[k], list):
                current_kwargs[k] = [current_kwargs[k]]
            current_kwargs[k].append(v)
        else:
            current_kwargs[k] = v

    return current_kwargs


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
            mu.migrate_image(tags[0])

        return images


class PodmanHpcContainersManager(ContainersManager):
    def __init__(self, site_config, **kwargs):
        self._site_config = site_config
        super().__init__(**kwargs)

        self._podman_hpc_modules = self._load_podman_hpc_modules()

    def _podman_hpc_env(self):
        env = {
            site_config_module._MOD_ENV: self._site_config.modules_dir,
        }

        return env

    def _podman_hpc_annotations(self):
        annotations = {site_config_module._HOOKS_ANNO: "true"}

        return annotations

    def _load_podman_hpc_modules(self):
        modules = {}

        for mod in Path(self._site_config.modules_dir).glob("*.yaml"):
            with mod.open() as fp:
                module_spec = yaml.safe_load(fp)
                modules[module_spec["cli_arg"]] = {
                    "env": module_spec["env"],
                    "additional_args": module_spec.get("additional_args", []),
                }

        return modules

    def _cli_arg_to_api_arg(self, arg: str) -> Dict[str, str]:
        cli_arg_to_api_arg = {
            "-e": "environment",
            "--ipc": "ipc_mode",
            "--network": "network_mode",
            "--pid": "pid_mode",
            "--privileged": "privileged",
            "--userns": "userns_mode",
        }

        arg_switch = arg
        arg_value = None

        # Try to split into switch and value
        for s in [" ", "="]:
            parts = arg.split(s, 1)
            if len(parts) == 2:
                (arg_switch, arg_value) = parts
                break

        # If its a switch with no value, set to True
        if arg_value is None:
            arg_value = True

        # Special case for environment variables with no value
        if arg_switch == "-e":
            if "=" not in arg_value:
                arg_value = {arg_value: "1"}
            # Convert to dict
            else:
                (k, v) = arg_value.split("=", 1)
                arg_value = {k: v}

        if arg_switch not in cli_arg_to_api_arg:
            raise ValueError(f"Unrecognized CLI option: {arg_switch}")

        return {cli_arg_to_api_arg[arg_switch]: arg_value}

    def _process_kwargs(self, kwargs) -> Tuple[Dict[str, str], Dict[str, str]]:
        env = {}
        additional_args = []
        args = {}

        podman_hpc_args = self._podman_hpc_modules.keys()

        for name in list(kwargs.keys()):
            value = kwargs[name]
            if name in podman_hpc_args and value:
                # Pop the arg so the super class doesn't see it
                kwargs.pop(name)
                env[self._podman_hpc_modules[name]["env"]] = "1"
                additional_args += self._podman_hpc_modules[name]["additional_args"]

        # Convert the CL args to API args
        for arg in additional_args:
            _add_kwargs(args, self._cli_arg_to_api_arg(arg))

        # Add the environment variables
        args.setdefault("environment", {}).update(env)

        return args

    def create(
        self,
        image: Union[Image, str],
        command: Union[str, List[str], None] = None,
        **kwargs,
    ) -> Container:
        print(kwargs)
        additional_args = self._process_kwargs(kwargs)
        print(kwargs)
        _add_kwargs(kwargs, additional_args)

        kwargs.setdefault("environment", {}).update(self._podman_hpc_env())
        kwargs.setdefault("annotations", {}).update(self._podman_hpc_annotations())

        print(kwargs)

        return super().create(image, command, **kwargs)

    def run(
        self,
        image: Union[str, Image],
        command: Union[str, List[str], None] = None,
        stdout=True,
        stderr=False,
        remove: bool = False,
        **kwargs,
    ) -> Union[Container, Union[Generator[str, None, None], Iterator[str]]]:
        return super().run(image, command, stdout, stderr, remove, **kwargs)


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


with PodmanHpcClient(base_url=uri) as client:
    version = client.version()
    # print("Release: ", version["Version"])
    # print("Compatible API: ", version["ApiVersion"])
    # print("Podman API: ", version["Components"][0]["Details"]["APIVersion"], "\n")
    info = client.info()
    # print(json.dumps(info))

    # Pull an image
    # '--root', '/images/70243_hpc/storage', '--runroot', '/tmp/70243_hpc', '--storage-opt', 'mount_program=/usr/bin/fuse-overlayfs-wrap', '--cgroup-manager', 'cgroupfs', '--storage-opt', 'ignore_chown_errors=true'
    # params = _pull_params()
    image = client.images.pull("registry.nersc.gov/library/nersc/mpi4py:3.1.3")
    log_config = {
        "Type": "json-file",
    }
    output = client.containers.run(
        image.id,
        command=["nvidia-smi"],
        stdout=True,
        stderr=True,
        log_config=log_config,
        gpu=True,
    )
    print(output)

    # container = client.containers.create(image.id, command=["echo", "Hello, World!"])
    # container.start()
    # exit_status = container.wait()
    # print(exit_status)
    # container.reload()

    # print(container.status)

    # for l in container.logs(stdout=True, stderr=True, stream=True):
    #     print(l)

    # print("Image: ", image)
