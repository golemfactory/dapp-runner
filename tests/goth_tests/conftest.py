"""Pytest configuration file containing the utilities for Dapp Runner goth tests."""
import asyncio
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Generator, List, cast
from uuid import uuid4

import pytest
import yaml

from goth.configuration import Configuration, Override, load_yaml
from goth.runner import Runner
from goth.runner.log import configure_logging
from goth.runner.probe import ProviderProbe, RequestorProbe


@pytest.fixture(scope="session")
def event_loop():
    """Make async fixtures use same event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()

    yield loop

    loop.close()


def _project_dir() -> Path:
    package_dir = Path(__file__).parent.parent
    return package_dir.parent.resolve()


def pytest_addoption(parser):
    """Add optional parameters to pytest CLI invocations."""

    parser.addoption(
        "--config-path",
        help="Path to the `goth-config.yml` file. (default: %(default)s)",
        default=_project_dir() / "tests" / "goth_tests" / "assets" / "goth-config.yml",
    )

    parser.addoption(
        "--config-override",
        action="append",
        help="Set an override for a value specified in goth-config.yml file. \
                This argument may be used multiple times. \
                Values must follow the convention: {yaml_path}={value}, e.g.: \
                `docker-compose.build-environment.release-tag=0.6.`",
    )


@pytest.fixture(scope="session")
def log_dir() -> Path:
    """Create log dir for goth test session."""
    base_dir = Path("/", "tmp", "goth-tests", "dapp-runner")
    date_str = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S-%f")
    log_dir = base_dir / f"goth_{date_str}"
    log_dir.mkdir(parents=True)
    return log_dir


@pytest.fixture(scope="session")
def goth_config_path(request: pytest.FixtureRequest) -> Path:
    """Return location of goth config."""
    return Path(request.config.option.config_path)


@pytest.fixture(scope="function")
def config_overrides(request: pytest.FixtureRequest) -> List[Override]:
    """Fixture parsing --config-override params passed to the test invocation.

    This fixture has "function" scope, which means that each test function will
    receive its own copy of the list of config overrides and may modify it at will,
    without affecting other test functions run in the same session.
    """

    overrides: List[str] = request.config.option.config_override or []
    return cast(List[Override], [tuple(o.split("=", 1)) for o in overrides])


@pytest.fixture(scope="function")
def goth_config(
    goth_config_path: Path,
    config_overrides: List[Override],
    goth_probe_use_proxy: bool,
) -> Configuration:
    """Apply changes to goth config."""
    # As `goth.configuration.load_yaml` dose not support overriding values inside a list
    # we are creating new config file with modifications to lists
    altered_goth_config_path = goth_config_path.parent / f"goth-config-altered-{uuid4()}.yml"
    with open(goth_config_path) as f:
        goth_config_dict = yaml.load(f, yaml.FullLoader)
    for node in goth_config_dict["nodes"]:
        node["use-proxy"] = goth_probe_use_proxy
    with open(altered_goth_config_path, "w") as f:
        yaml.dump(goth_config_dict, f)

    goth_config = load_yaml(altered_goth_config_path, config_overrides)
    return goth_config


@pytest.fixture
def goth_probe_use_proxy(request: pytest.FixtureRequest) -> bool:
    """Allow to control if goth probe instances will be configured to use proxy.

    Can be set using `pytest.mark.parametrize` with `indirect` set to `True`.
    `@pytest.mark.parametrize("goth_probe_use_proxy", [...], indirect=True)`
    Defaults to True.
    """
    return getattr(request, "param", True)


@pytest.fixture
async def goth_runner(
    log_dir: Path,
    goth_config: Configuration,
) -> AsyncGenerator[Runner, None]:
    """Initialize goth runner and returns it."""
    configure_logging(log_dir)
    runner = Runner(base_log_dir=log_dir, compose_config=goth_config.compose_config)
    async with runner(goth_config.containers):
        yield runner


@pytest.fixture
def goth_requestor_probe(goth_runner: Runner) -> Generator[RequestorProbe, None, None]:
    """Get and return requestor probe from goth runner."""
    requestor = goth_runner.get_probes(probe_type=RequestorProbe)[0]
    yield requestor


@pytest.fixture
def goth_provider_probes(goth_runner: Runner) -> Generator[List[ProviderProbe], None, None]:
    """Get and return provider probes from goth runner."""
    providers = goth_runner.get_probes(probe_type=ProviderProbe)
    yield providers
