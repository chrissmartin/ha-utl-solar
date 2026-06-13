"""Tests for the UTL Solar sync-history button."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.utl_solar.button import UTLSolarSyncHistoryButton
from custom_components.utl_solar.coordinator import (
    UTLSolarCoordinator,
    UTLSolarRateLimitError,
)


def _make_button(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> UTLSolarSyncHistoryButton:
    mock_config_entry.add_to_hass(hass)
    coordinator = UTLSolarCoordinator(hass, mock_config_entry)
    return UTLSolarSyncHistoryButton(coordinator, mock_config_entry)


async def test_fetch_month_retries_after_rate_limit(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A 429 triggers a single backoff-and-retry that then succeeds."""
    button = _make_button(hass, mock_config_entry)
    button._coordinator.async_fetch_monthly_production = AsyncMock(
        side_effect=[
            UTLSolarRateLimitError(retry_after=3.0),
            [{"date": "1", "PvProduction": 5.0}],
        ]
    )

    with patch("custom_components.utl_solar.button.asyncio.sleep", new=AsyncMock()) as sleep_mock:
        result = await button._async_fetch_month(2024, 1)

    assert result == [{"date": "1", "PvProduction": 5.0}]
    assert button._coordinator.async_fetch_monthly_production.call_count == 2
    sleep_mock.assert_awaited_once_with(3.0)


async def test_fetch_month_second_rate_limit_propagates(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A second consecutive 429 propagates (so the caller skips the month)."""
    button = _make_button(hass, mock_config_entry)
    button._coordinator.async_fetch_monthly_production = AsyncMock(
        side_effect=UTLSolarRateLimitError(retry_after=1.0)
    )

    with (
        patch("custom_components.utl_solar.button.asyncio.sleep", new=AsyncMock()),
        pytest.raises(UpdateFailed),
    ):
        await button._async_fetch_month(2024, 1)

    assert button._coordinator.async_fetch_monthly_production.call_count == 2


async def test_fetch_month_caps_retry_after(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """An absurd Retry-After is capped at HISTORY_SYNC_MAX_RETRY_AFTER."""
    button = _make_button(hass, mock_config_entry)
    button._coordinator.async_fetch_monthly_production = AsyncMock(
        side_effect=[UTLSolarRateLimitError(retry_after=99999.0), []]
    )

    with patch("custom_components.utl_solar.button.asyncio.sleep", new=AsyncMock()) as sleep_mock:
        await button._async_fetch_month(2024, 1)

    sleep_mock.assert_awaited_once_with(60.0)
