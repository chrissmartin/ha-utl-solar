"""Config flow for UTL Solar integration."""

from __future__ import annotations

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_BASE_URL, API_LOGIN, DEFAULT_DEVICE_ID, DOMAIN

_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


class UTLSolarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for UTL Solar."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                session = async_get_clientsession(self.hass)
                async with session.post(
                    f"{API_BASE_URL}{API_LOGIN}",
                    json={
                        "email": user_input["email"],
                        "password": user_input["password"],
                    },
                    headers={
                        "Content-Type": "application/json",
                        "X-Device-Id": DEFAULT_DEVICE_ID,
                    },
                    timeout=_REQUEST_TIMEOUT,
                ) as resp:
                    data = await resp.json(content_type=None)
                    if resp.status == 200 and data.get("success"):
                        await self.async_set_unique_id(user_input["email"])
                        self._abort_if_unique_id_configured()

                        return self.async_create_entry(
                            title=f"UTL Solar ({user_input['email']})",
                            data=user_input,
                        )
                    errors["base"] = "invalid_auth"
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"

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
