"""Data update coordinator for UTL Solar."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from email.utils import parsedate_to_datetime

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
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
    CONF_SCAN_INTERVAL,
    DEFAULT_DEVICE_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    NIGHT_END_HOUR,
    NIGHT_SCAN_INTERVAL,
    NIGHT_START_HOUR,
)

_LOGGER = logging.getLogger(__name__)

_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


class UTLSolarRateLimitError(UpdateFailed):
    """Raised when the API responds with HTTP 429 (too many requests).

    Subclasses ``UpdateFailed`` so ordinary polling treats it as a transient
    failure, while callers that want to back off can inspect ``retry_after``.
    """

    def __init__(self, retry_after: float | None = None) -> None:
        """Store the server-advised backoff, in seconds, if provided."""
        super().__init__("Rate limited by UTL Solar RMS (HTTP 429)")
        self.retry_after = retry_after


def _parse_retry_after(value: str | None) -> float | None:
    """Parse a Retry-After header (delta-seconds or HTTP-date) to seconds."""
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        retry_dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if retry_dt is None:
        return None
    return max(0.0, (retry_dt - dt_util.utcnow()).total_seconds())


class UTLSolarCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator to fetch data from UTL Solar RMS API."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
            config_entry=entry,
        )
        self._email = entry.data["email"]
        self._password = entry.data["password"]
        self._day_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        self._token: str | None = None
        self._auth_lock = asyncio.Lock()

    async def _async_login(self) -> str:
        """Authenticate and return JWT token."""
        async with self._auth_lock:
            # Another coroutine may have just refreshed the token.
            if self._token:
                return self._token

            session = async_get_clientsession(self.hass)
            try:
                async with session.post(
                    f"{API_BASE_URL}{API_LOGIN}",
                    json={"email": self._email, "password": self._password},
                    headers={
                        "Content-Type": "application/json",
                        "X-Device-Id": DEFAULT_DEVICE_ID,
                    },
                    timeout=_REQUEST_TIMEOUT,
                ) as resp:
                    if resp.status in (401, 403):
                        raise ConfigEntryAuthFailed(
                            f"Invalid UTL Solar credentials (status {resp.status})"
                        )
                    if resp.status != 200:
                        raise UpdateFailed(f"Login failed with status {resp.status}")
                    data = await resp.json(content_type=None)
                    if not data.get("success"):
                        raise ConfigEntryAuthFailed(
                            f"Login rejected: {data.get('message', 'Unknown error')}"
                        )
                    token = data.get("token")
                    if not token:
                        raise UpdateFailed("Login response did not include a token")
                    self._token = token
                    return token
            except aiohttp.ClientError as err:
                raise UpdateFailed(f"Connection error during login: {err}") from err
            except TimeoutError as err:
                raise UpdateFailed("Login timed out") from err

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
                method,
                f"{API_BASE_URL}{endpoint}",
                headers=headers,
                json=json_data,
                timeout=_REQUEST_TIMEOUT,
            ) as resp:
                if resp.status == 429:
                    raise UTLSolarRateLimitError(
                        _parse_retry_after(resp.headers.get("Retry-After"))
                    )
                if resp.status in (401, 403):
                    _LOGGER.debug("Token expired, re-authenticating")
                    self._token = None
                    await self._async_login()
                    headers["Authorization"] = f"Bearer {self._token}"
                    async with session.request(
                        method,
                        f"{API_BASE_URL}{endpoint}",
                        headers=headers,
                        json=json_data,
                        timeout=_REQUEST_TIMEOUT,
                    ) as retry_resp:
                        if retry_resp.status == 429:
                            raise UTLSolarRateLimitError(
                                _parse_retry_after(retry_resp.headers.get("Retry-After"))
                            )
                        if retry_resp.status in (401, 403):
                            raise ConfigEntryAuthFailed(
                                "Authentication rejected after token refresh"
                            )
                        if retry_resp.status != 200:
                            raise UpdateFailed(
                                f"API request failed after re-auth: {retry_resp.status}"
                            )
                        return await retry_resp.json(content_type=None)
                if resp.status != 200:
                    raise UpdateFailed(f"API request failed: {resp.status}")
                return await resp.json(content_type=None)
        except TimeoutError as err:
            raise UpdateFailed(f"Request to {endpoint} timed out") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Connection error: {err}") from err

    async def _async_update_data(self) -> dict:
        """Fetch latest data from UTL Solar RMS."""
        # Re-evaluate the poll cadence first so the interval still tracks
        # time-of-day even when the fetches below fail (e.g. overnight outages).
        self._adjust_update_interval()

        # Fetch devices and plant in parallel for faster updates.
        devices_result: dict | None = None
        plant_result: dict | None = None

        async def _fetch_devices() -> dict | None:
            try:
                return await self._async_request("GET", API_DEVICES)
            except UpdateFailed as err:
                _LOGGER.warning("Failed to fetch devices: %s", err)
                return None

        async def _fetch_plant() -> dict | None:
            try:
                return await self._async_request("GET", API_PLANT)
            except UpdateFailed as err:
                _LOGGER.warning("Failed to fetch plant: %s", err)
                return None

        devices_result, plant_result = await asyncio.gather(_fetch_devices(), _fetch_plant())

        if devices_result is None and plant_result is None:
            raise UpdateFailed("All API requests failed")

        inverter = {}
        logger_sno = None
        if devices_result and devices_result.get("inverter"):
            inverter = devices_result["inverter"][0]
            logger_sno = inverter.get("logger_sno")

        plant_data = {}
        if isinstance(plant_result, list) and plant_result:
            plant_data = plant_result[0]
        elif isinstance(plant_result, dict) and plant_result:
            plant_data = plant_result

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

    def _adjust_update_interval(self) -> None:
        """Slow down polling at night when there's no solar production."""
        hour = dt_util.now().hour
        if hour >= NIGHT_START_HOUR or hour < NIGHT_END_HOUR:
            new_interval = timedelta(seconds=NIGHT_SCAN_INTERVAL)
        else:
            new_interval = timedelta(seconds=self._day_interval)
        if self.update_interval != new_interval:
            _LOGGER.debug("Switching update interval to %s", new_interval)
            self.update_interval = new_interval

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
        if self.data:
            plant = self.data.get("plant") or {}
            plant_id = plant.get("plant_id") or plant.get("id")
            if plant_id is None:
                plant_id = (self.data.get("inverter") or {}).get("plantId")
            if plant_id is not None:
                return plant_id
        raise UpdateFailed("No plant ID available — run a data refresh first")
