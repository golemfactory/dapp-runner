"""Pytest configuration file containing the utilities for Dapp Runner goth tests."""
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, List, cast

import pytest

from goth.configuration import Override, load_yaml
from goth.runner import Runner
from goth.runner.log import configure_logging
from goth.runner.probe import RequestorProbe


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

    parser.addoption(
        "--ssh-verify-connection",
        action="store_true",
        help="in the `test_run_ssh.py`, peform an actual SSH connection through "
        "the exposed websocket. Requires both `ssh` and `websocket` binaries "
        "to be available in the path.",
    )


@pytest.fixture(scope="session")
def log_dir() -> Path:
    """Create log dir for goth test session."""
    base_dir = Path("/", "tmp", "goth-tests", "dapp-runner")
    date_str = datetime.utcnow().isoformat(sep="_", timespec="minutes")
    log_dir = base_dir / f"goth_{date_str}"
    log_dir.mkdir(parents=True)
    return log_dir


@pytest.fixture(scope="session")
def goth_config_path(request: pytest.FixtureRequest) -> Path:
    """Return location of goth config."""
    return request.config.option.config_path


@pytest.fixture(scope="function")
def config_overrides(request: pytest.FixtureRequest) -> List[Override]:
    """Fixture parsing --config-override params passed to the test invocation.

    This fixture has "function" scope, which means that each test function will
    receive its own copy of the list of config overrides and may modify it at will,
    without affecting other test functions run in the same session.
    """

    overrides: List[str] = request.config.option.config_override or []
    return cast(List[Override], [tuple(o.split("=", 1)) for o in overrides])


@pytest.fixture
async def goth_runner(
    log_dir: Path,
    goth_config_path: Path,
    config_overrides: List[Override],
) -> AsyncGenerator[Runner, None]:
    """Initialize goth runner and returns it."""
    config = load_yaml(goth_config_path, config_overrides)
    configure_logging(log_dir)
    runner = Runner(base_log_dir=log_dir, compose_config=config.compose_config)
    async with runner(config.containers):
        yield runner


@pytest.fixture
def goth_requestor_probe(goth_runner: Runner) -> RequestorProbe:
    """Get and return requestor probe from goth runner."""
    requestor = goth_runner.get_probes(probe_type=RequestorProbe)[0]
    yield requestor
