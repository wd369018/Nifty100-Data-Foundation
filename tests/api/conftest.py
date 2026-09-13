"""Pytest fixtures for API tests.

NIFTY100_LINK_CHECK is disabled so the documents endpoint never performs
live HEAD requests during the test run.
"""

import os

os.environ.setdefault("NIFTY100_LINK_CHECK", "0")

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app


@pytest.fixture(scope="session")
def client():
    return TestClient(create_app())
