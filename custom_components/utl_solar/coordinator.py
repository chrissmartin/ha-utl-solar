"""Data update coordinator for UTL Solar."""

from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    API_BASE_URL,
    API_DEVICE_DAILY_CHART,
    API_DEVICES,
    API_LOGIN,
    API_PLANT,
    API_PLANT_DAILY_CHART,
    API_PLANT_MONTHLY_CHART,
    DEFAULT_DEVICE_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class UTLSolarCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator to fetch data from UTL Solar RMS API."""

    def __init__(self, hass: HomeAssistant, email: str, password: str) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._email = email
        self._password = password
        self._token: str | None = None

    async def _async_login(self) -> str:
        """Authenticate and return JWT token."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.post(
                f"{API_BASE_URL}{API_LOGIN}",
                json={"email": self._email, "password": self._password},
                headers={
                    "Content-Type": "application/json",
                    "X-Device-Id": DEFAULT_DEVICE_ID,
                },
            ) as resp:
                if resp.status != 200:
                    raise UpdateFailed(f"Login failed with status {resp.status}")
                data = await resp.json(content_type=None)
                if not data.get("success"):
                    raise UpdateFailed(f"Login failed: {data.get('message', 'Unknown error')}")
                self._token = data["token"]
                return self._token
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Connection error during login: {err}") from err

    async def _async_request(
        self, method: str, endpoint: str, json_data: dict | None = None
    ) -> dict:
        """Make an authenticated API request with auto token refresh."""
        if not self._token:
            await self._async_login()

        session = async_get_clientsession(self.hass)
        headers = {
            "Content-Type": "application/json",
            "X-Device-Id": DEFAULT_DEVICE_ID,
            "Authorization": f"Bearer {self._token}",
        }

        try:
            async with session.request(
                method, f"{API_BASE_URL}{endpoint}", headers=headers, json=json_data
            ) as resp:
                if resp.status in (401, 403):
                    _LOGGER.debug("Token expired, re-authenticating")
                    await self._async_login()
                    headers["Authorization"] = f"Bearer {self._token}"
                    async with session.request(
                        method,
                        f"{API_BASE_URL}{endpoint}",
                        headers=headers,
                        json=json_data,
                    ) as retry_resp:
                        if retry_resp.status != 200:
                            raise UpdateFailed(
                                f"API request failed after re-auth: {retry_resp.status}"
                            )
                        return await retry_resp.json(content_type=None)
                if resp.status != 200:
                    raise UpdateFailed(f"API request failed: {resp.status}")
                return await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Connection error: {err}") from err

    async def _async_update_data(self) -> dict:
        """Fetch latest data from UTL Solar RMS."""
        devices = await self._async_request("GET", API_DEVICES)
        plant = await self._async_request("GET", API_PLANT)

        inverter = {}
        logger_sno = None
        if devices.get("inverter"):
            inverter = devices["inverter"][0]
            logger_sno = inverter.get("logger_sno")

        plant_data = {}
        if isinstance(plant, list) and plant:
            plant_data = plant[0]

        realtime = {}
        if logger_sno:
            today = dt_util.now().strftime("%Y-%m-%d")
            try:
                chart = await self._async_request(
                    "POST",
                    API_DEVICE_DAILY_CHART,
                    {
                        "device_sn": logger_sno,
                        "date_parameter": today,
                    },
                )
                results = chart.get("results", [])
                if results:
                    realtime = results[-1]
            except UpdateFailed:
                _LOGGER.warning("Failed to fetch device daily chart")

        return {
            "inverter": inverter,
            "plant": plant_data,
            "realtime": realtime,
        }

    async def async_fetch_monthly_production(self, year: int, month: int) -> list[dict]:
        """Fetch daily production totals for a given month."""
        date_param = f"{year}-{month:02d}"
        data = await self._async_request(
            "POST",
            API_PLANT_MONTHLY_CHART,
            {
                "plant_id": self._get_plant_id(),
                "date_parameter": date_param,
            },
        )
        return data.get("results", [])

    async def async_fetch_daily_power_curve(self, date_str: str) -> list[dict]:
        """Fetch 5-min power curve for a specific day."""
        data = await self._async_request(
            "POST",
            API_PLANT_DAILY_CHART,
            {
                "plant_id": self._get_plant_id(),
                "date_parameter": date_str,
            },
        )
        return data.get("results", [])

    def _get_plant_id(self) -> int:
        """Get the plant ID from cached data."""
        if self.data and self.data.get("plant"):
            return self.data["plant"].get("plant_id", self.data["plant"].get("id"))
        if self.data and self.data.get("inverter"):
            return self.data["inverter"].get("plantId")
        raise UpdateFailed("No plant ID available — run a data refresh first")
