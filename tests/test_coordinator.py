"""Tests for the UTL Solar data update coordinator."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.utl_solar.const import (
    API_BASE_URL,
    API_DEVICE_DAILY_CHART,
    API_DEVICES,
    API_PLANT,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    NIGHT_SCAN_INTERVAL,
)
from custom_components.utl_solar.coordinator import (
    UTLSolarCoordinator,
    UTLSolarRateLimitError,
    _parse_retry_after,
)

from .conftest import LOGIN_URL

DEVICES_URL = f"{API_BASE_URL}{API_DEVICES}"
PLANT_URL = f"{API_BASE_URL}{API_PLANT}"
CHART_URL = f"{API_BASE_URL}{API_DEVICE_DAILY_CHART}"


def _make_coordinator(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> UTLSolarCoordinator:
    mock_config_entry.add_to_hass(hass)
    return UTLSolarCoordinator(hass, mock_config_entry)


async def test_login_invalid_credentials_raises_auth_failed(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A 401 from the login endpoint raises ConfigEntryAuthFailed."""
    aioclient_mock.post(LOGIN_URL, status=401)
    coordinator = _make_coordinator(hass, mock_config_entry)

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_login()


async def test_login_rejected_raises_auth_failed(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A success:false body raises ConfigEntryAuthFailed."""
    aioclient_mock.post(LOGIN_URL, json={"success": False, "message": "nope"})
    coordinator = _make_coordinator(hass, mock_config_entry)

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_login()


async def test_login_missing_token_raises_update_failed(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A success:true body without a token raises UpdateFailed, not KeyError."""
    aioclient_mock.post(LOGIN_URL, json={"success": True})
    coordinator = _make_coordinator(hass, mock_config_entry)

    with pytest.raises(UpdateFailed):
        await coordinator._async_login()


async def test_login_caches_token(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A second login reuses the cached token without another HTTP request."""
    aioclient_mock.post(LOGIN_URL, json={"success": True, "token": "jwt-123"})
    coordinator = _make_coordinator(hass, mock_config_entry)

    assert await coordinator._async_login() == "jwt-123"
    assert await coordinator._async_login() == "jwt-123"
    assert aioclient_mock.call_count == 1


def test_get_plant_id_from_plant(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """plant_id is read from the plant payload."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    coordinator.data = {"plant": {"plant_id": 7}}
    assert coordinator._get_plant_id() == 7


def test_get_plant_id_falls_back_to_inverter(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """plant_id falls back to the inverter payload when plant lacks it."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    coordinator.data = {"plant": {}, "inverter": {"plantId": 42}}
    assert coordinator._get_plant_id() == 42


def test_get_plant_id_raises_when_unavailable(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A missing plant id raises UpdateFailed rather than returning None."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    coordinator.data = {"plant": {}, "inverter": {}}
    with pytest.raises(UpdateFailed):
        coordinator._get_plant_id()


@pytest.mark.parametrize(
    ("hour", "expected"),
    [
        (3, NIGHT_SCAN_INTERVAL),  # before NIGHT_END_HOUR
        (12, DEFAULT_SCAN_INTERVAL),  # daytime
        (20, NIGHT_SCAN_INTERVAL),  # after NIGHT_START_HOUR
    ],
)
def test_adjust_update_interval(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hour: int,
    expected: int,
) -> None:
    """The poll interval slows down at night and speeds up during the day."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    with patch(
        "custom_components.utl_solar.coordinator.dt_util.now",
        return_value=datetime(2026, 6, 13, hour, 0, 0),
    ):
        coordinator._adjust_update_interval()
    assert coordinator.update_interval == timedelta(seconds=expected)


async def test_update_data_happy_path(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A full refresh assembles inverter, plant and realtime data."""
    aioclient_mock.post(LOGIN_URL, json={"success": True, "token": "jwt-123"})
    aioclient_mock.get(
        DEVICES_URL,
        json={"inverter": [{"logger_sno": "LG1", "solar_power": 3.2}]},
    )
    aioclient_mock.get(PLANT_URL, json=[{"plant_id": 7, "on_grid_status": "On-Grid"}])
    aioclient_mock.post(CHART_URL, json={"results": [{"ac_voltage_a": 230.5}]})

    coordinator = _make_coordinator(hass, mock_config_entry)
    data = await coordinator._async_update_data()

    assert data["inverter"]["solar_power"] == 3.2
    assert data["plant"]["plant_id"] == 7
    assert data["realtime"]["ac_voltage_a"] == 230.5


async def test_update_data_all_requests_fail(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """If both core requests fail the update raises UpdateFailed."""
    aioclient_mock.post(LOGIN_URL, json={"success": True, "token": "jwt-123"})
    aioclient_mock.get(DEVICES_URL, status=500)
    aioclient_mock.get(PLANT_URL, status=500)

    coordinator = _make_coordinator(hass, mock_config_entry)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("10", 10.0),
        ("0", 0.0),
        (None, None),
        ("not-a-date", None),
        ("Wed, 21 Oct 2015 07:28:00 GMT", 0.0),  # a past date clamps to 0
    ],
)
def test_parse_retry_after(header: str | None, expected: float | None) -> None:
    """Retry-After parses delta-seconds and HTTP-date forms, else None."""
    assert _parse_retry_after(header) == expected


async def test_request_raises_rate_limit_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A 429 response raises UTLSolarRateLimitError carrying the backoff."""
    aioclient_mock.post(LOGIN_URL, json={"success": True, "token": "jwt-123"})
    aioclient_mock.get(DEVICES_URL, status=429, headers={"Retry-After": "5"})

    coordinator = _make_coordinator(hass, mock_config_entry)
    with pytest.raises(UTLSolarRateLimitError) as exc_info:
        await coordinator._async_request("GET", API_DEVICES)

    assert exc_info.value.retry_after == 5.0
    # It is also an UpdateFailed, so normal polling treats it as transient.
    assert isinstance(exc_info.value, UpdateFailed)


def test_day_interval_uses_configured_option(hass: HomeAssistant) -> None:
    """The daytime interval honors the scan_interval option."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@example.com",
        data={"email": "user@example.com", "password": "secret"},
        options={CONF_SCAN_INTERVAL: 120},
    )
    entry.add_to_hass(hass)
    coordinator = UTLSolarCoordinator(hass, entry)

    with patch(
        "custom_components.utl_solar.coordinator.dt_util.now",
        return_value=datetime(2026, 6, 13, 12, 0, 0),
    ):
        coordinator._adjust_update_interval()

    assert coordinator.update_interval == timedelta(seconds=120)
