"""SDK import / smoke tests (no running server required for import)."""

from __future__ import annotations

import pytest

from physical_ai_sdk import RuntimeClient, RuntimeClientError, __version__


def test_import_and_version() -> None:
    assert __version__
    client = RuntimeClient()
    assert client.base_url == "http://127.0.0.1:8000"


def test_unreachable_runtime_raises() -> None:
    client = RuntimeClient("http://127.0.0.1:59999", timeout=0.5)
    with pytest.raises(RuntimeClientError):
        client.health()
