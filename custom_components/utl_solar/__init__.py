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
    coordinator = UTLSolarCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = UTLSolarData(coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: UTLSolarConfigEntry) -> None:
    """Reload the entry when its options change (e.g. the poll interval)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: UTLSolarConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
