"""Shared fixtures for UTL Solar tests."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.utl_solar.const import API_BASE_URL, API_LOGIN, DOMAIN

LOGIN_URL = f"{API_BASE_URL}{API_LOGIN}"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(recorder_mock, enable_custom_integrations):
    """Enable loading of the custom integration with a recorder available.

    ``recorder_mock`` is resolved first so the in-memory recorder DB is created
    before ``hass`` starts (it asserts ``hass`` is not yet set up). The
    integration declares ``recorder`` as a dependency, so it must be present
    whenever a config entry is set up.
    """
    yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry for the integration."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@example.com",
        title="UTL Solar (user@example.com)",
        data={"email": "user@example.com", "password": "secret"},
    )
