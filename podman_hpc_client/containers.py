from typing import Dict, List, Union, Generator, Iterator, Tuple
from pathlib import Path
import os

import yaml

from podman.client import (
    ContainersManager,
)
from podman.domain.images import Image
from podman.domain.containers import Container

from podman_hpc import siteconfig as site_config_module


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

    # We need to emulate the behavior of the podman cli that will resolve
    # environment variables without a value or *suffix from the host environment
    # its a little odd, but the best we can do is to resolve it here, you
    # could argue that it should be done from the environment that is running
    # podman-hpc system service, but that would require changes to podman-hpc.
    def _resolve_host_env(self, env: Dict[str, str]) -> Dict[str, str]:
        for name in list(env.keys()):
            value = env[name]
            if value is None:
                # First remove the key
                del env[name]
                # If we have a host environment variable, add it
                if name in os.environ:
                    env[name] = os.environ[name]
                # If we have a host environment variables with the suffix add them
                elif name.endswith("*"):
                    prefix = name[:-1]
                    for k in os.environ.keys():
                        if k.startswith(prefix):
                            env[k] = os.environ[k]

        return env

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
                arg_value = {arg_value: None}
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
        additional_args = self._process_kwargs(kwargs)
        _add_kwargs(kwargs, additional_args)

        kwargs.setdefault("environment", {}).update(self._podman_hpc_env())
        # Resolve any host environment variables
        kwargs["environment"] = self._resolve_host_env(kwargs["environment"])
        kwargs.setdefault("annotations", {}).update(self._podman_hpc_annotations())

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
