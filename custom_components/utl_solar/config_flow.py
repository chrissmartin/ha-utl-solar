"""Config flow for UTL Solar integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    API_BASE_URL,
    API_LOGIN,
    CONF_SCAN_INTERVAL,
    DEFAULT_DEVICE_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


async def _async_validate_credentials(hass, email: str, password: str) -> str | None:
    """Validate credentials. Return an error key, or None on success."""
    session = async_get_clientsession(hass)
    try:
        async with session.post(
            f"{API_BASE_URL}{API_LOGIN}",
            json={"email": email, "password": password},
            headers={
                "Content-Type": "application/json",
                "X-Device-Id": DEFAULT_DEVICE_ID,
            },
            timeout=_REQUEST_TIMEOUT,
        ) as resp:
            data = await resp.json(content_type=None)
            if resp.status == 200 and data.get("success") and data.get("token"):
                return None
            return "invalid_auth"
    except (aiohttp.ClientError, TimeoutError):
        return "cannot_connect"


class UTLSolarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for UTL Solar."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._reauth_email: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return UTLSolarOptionsFlow()

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input["email"])
            self._abort_if_unique_id_configured()

            error = await _async_validate_credentials(
                self.hass, user_input["email"], user_input["password"]
            )
            if error is None:
                return self.async_create_entry(
                    title=f"UTL Solar ({user_input['email']})",
                    data=user_input,
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("email"): str,
                    vol.Required("password"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Handle re-authentication when stored credentials stop working."""
        self._reauth_email = entry_data["email"]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Confirm re-authentication with a fresh password."""
        errors: dict[str, str] = {}

        if user_input is not None:
            error = await _async_validate_credentials(
                self.hass, self._reauth_email, user_input["password"]
            )
            if error is None:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={
                        "email": self._reauth_email,
                        "password": user_input["password"],
                    },
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required("password"): str}),
            description_placeholders={"email": self._reauth_email},
            errors=errors,
        )


class UTLSolarOptionsFlow(OptionsFlow):
    """Handle UTL Solar options (daytime poll interval)."""

    async def async_step_init(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    ),
                }
            ),
        )
