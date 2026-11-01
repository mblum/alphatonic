import ipaddress
import os
import socket
from contextlib import contextmanager
from pathlib import Path

import pytest
from hypothesis import settings

from alphatonic import EvaluationConfig, evaluate
from tests.support.panels import market

settings.register_profile("ci", max_examples=40, derandomize=True, deadline=None)
settings.register_profile("extended", max_examples=400, deadline=None)

E2E_DIR = Path(__file__).parent / "e2e"


def pytest_addoption(parser):
    parser.addoption(
        "--extended",
        action="store_true",
        help="also run the slow, expanded experiments (marker: slow)",
    )
    parser.addoption(
        "--run-browser",
        action="store_true",
        help="also run the browser journeys in tests/e2e (needs pytest-playwright)",
    )


def pytest_ignore_collect(collection_path, config):
    # Ignore the directory before collection so that its Playwright imports never run by default.
    if collection_path == E2E_DIR and not config.getoption("run_browser"):
        return True
    return None


def pytest_collection_modifyitems(config, items):
    if config.getoption("extended"):
        return
    selected = [item for item in items if item.get_closest_marker("slow") is None]
    deselected = [item for item in items if item.get_closest_marker("slow") is not None]
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    # Small resampling matrices otherwise pay thread-pool launch costs on old OpenBLAS.
    # Bound subprocess resources consistently across supported dependency environments.
    monkeypatch.setenv("OPENBLAS_NUM_THREADS", "1")
    monkeypatch.setenv("MKL_NUM_THREADS", "1")
    monkeypatch.setenv("VECLIB_MAXIMUM_THREADS", "1")
    guard = str(Path(__file__).parent / "support")
    monkeypatch.setenv("PYTHONPATH", guard + os.pathsep + os.environ.get("PYTHONPATH", ""))
    original = socket.socket.connect

    def connect(sock, address):
        if (
            sock.family in (socket.AF_INET, socket.AF_INET6)
            and not ipaddress.ip_address(address[0]).is_loopback
        ):
            raise AssertionError(f"External network prohibited: {address}")
        return original(sock, address)

    monkeypatch.setattr(socket.socket, "connect", connect)


@pytest.fixture
def panel():
    return market()


@pytest.fixture
def config():
    return EvaluationConfig(
        horizons=(1, 3),
        min_assets=3,
        hac_lags=2,
        quantiles=3,
        persistence={"lags": (1, 3, 200)},
        time_series={
            "target": "return",
            "min_pairs": 3,
            "min_horizons": 1,
            "min_coverage": 0.5,
            "rolling_window": "20D",
            "rolling_step": "10D",
            "bootstrap_samples": 0,
        },
    )


@pytest.fixture
def result(panel, config):
    return evaluate(*panel, config)


@pytest.fixture
def progress_log():
    events = []

    @contextmanager
    def progress(description, total=None):
        events.append(("open", description, total))

        def advance(steps=1, **kwargs):
            events.append(("advance", steps, kwargs))

        try:
            yield advance
        finally:
            events.append(("close", description))

    return progress, events
