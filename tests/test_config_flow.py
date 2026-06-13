"""Tests for the UTL Solar config flow."""

from __future__ import annotations

import pytest
import voluptuous as vol
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.utl_solar.const import CONF_SCAN_INTERVAL, DOMAIN

from .conftest import LOGIN_URL


async def test_user_flow_success(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """A valid login creates a config entry."""
    aioclient_mock.post(LOGIN_URL, json={"success": True, "token": "jwt-123"})

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"email": "user@example.com", "password": "secret"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "UTL Solar (user@example.com)"
    assert result["data"] == {"email": "user@example.com", "password": "secret"}
    assert result["result"].unique_id == "user@example.com"


async def test_user_flow_invalid_auth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A rejected login surfaces an invalid_auth error and stays on the form."""
    aioclient_mock.post(LOGIN_URL, json={"success": False, "message": "bad creds"})

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"email": "user@example.com", "password": "wrong"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_missing_token_is_invalid_auth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A success response with no token is treated as invalid auth."""
    aioclient_mock.post(LOGIN_URL, json={"success": True})

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"email": "user@example.com", "password": "secret"},
    )

    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A network error surfaces a cannot_connect error."""
    aioclient_mock.post(LOGIN_URL, exc=TimeoutError)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"email": "user@example.com", "password": "secret"},
    )

    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A duplicate account aborts before hitting the API."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"email": "user@example.com", "password": "secret"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # The unique-id check short-circuits before any login request is made.
    assert aioclient_mock.call_count == 0


async def test_reauth_flow_success(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Reauth updates the stored password and aborts successfully."""
    mock_config_entry.add_to_hass(hass)
    aioclient_mock.post(LOGIN_URL, json={"success": True, "token": "jwt-new"})

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"password": "new-secret"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data["password"] == "new-secret"


async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Reauth with bad credentials re-shows the form with an error."""
    mock_config_entry.add_to_hass(hass)
    aioclient_mock.post(LOGIN_URL, json={"success": False})

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"password": "still-wrong"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert mock_config_entry.data["password"] == "secret"


async def test_options_flow(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """The options flow stores a custom daytime scan interval."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 120}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_SCAN_INTERVAL] == 120


async def test_options_flow_rejects_out_of_range(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The options flow rejects an interval below the allowed minimum."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    with pytest.raises(vol.Invalid):
        await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_SCAN_INTERVAL: 5}
        )
