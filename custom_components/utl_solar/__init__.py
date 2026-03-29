"""UTL Solar integration for Home Assistant."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import UTLSolarCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BUTTON]


@dataclass
class UTLSolarData:
    """Runtime data for the UTL Solar integration."""

    coordinator: UTLSolarCoordinator


type UTLSolarConfigEntry = ConfigEntry[UTLSolarData]


async def async_setup_entry(hass: HomeAssistant, entry: UTLSolarConfigEntry) -> bool:
    """Set up UTL Solar from a config entry."""
    coordinator = UTLSolarCoordinator(
        hass,
        email=entry.data["email"],
        password=entry.data["password"],
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = UTLSolarData(coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: UTLSolarConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
