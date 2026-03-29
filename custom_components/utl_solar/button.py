"""Button platform for UTL Solar — historical data sync."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.components.button import ButtonEntity
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import UTLSolarConfigEntry
from .const import DOMAIN
from .coordinator import UTLSolarCoordinator

_LOGGER = logging.getLogger(__name__)

STATISTIC_ID = f"{DOMAIN}:daily_production"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UTLSolarConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up UTL Solar buttons from a config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([UTLSolarSyncHistoryButton(coordinator, entry)])


class UTLSolarSyncHistoryButton(ButtonEntity):
    """Button to sync historical solar production data."""

    _attr_has_entity_name = True
    _attr_translation_key = "sync_history"
    _attr_icon = "mdi:history"

    def __init__(self, coordinator: UTLSolarCoordinator, entry: UTLSolarConfigEntry) -> None:
        """Initialize the button."""
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_sync_history"

        inverter = coordinator.data.get("inverter", {}) if coordinator.data else {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="UTL Solar Inverter",
            manufacturer="UTL",
            model=inverter.get("device_type", "Solar Inverter"),
            serial_number=inverter.get("inverter_sno", "unknown"),
        )

    async def async_press(self) -> None:
        """Handle button press — sync historical data into recorder statistics."""
        _LOGGER.info("UTL Solar: starting historical data sync")

        plant = self._coordinator.data.get("plant", {}) if self._coordinator.data else {}
        creation = plant.get("creation_date") or plant.get("on_grid_date")
        if creation:
            try:
                start_date = datetime.strptime(creation, "%Y-%m-%d").date()
            except ValueError:
                start_date = (dt_util.now() - timedelta(days=365)).date()
        else:
            start_date = (dt_util.now() - timedelta(days=365)).date()

        end_date = dt_util.now().date()
        _LOGGER.info("UTL Solar: syncing %s -> %s", start_date, end_date)

        stats: list[StatisticData] = []
        cumulative = 0.0
        current = start_date.replace(day=1)

        while current <= end_date:
            year, month = current.year, current.month
            try:
                monthly = await self._coordinator.async_fetch_monthly_production(year, month)
                _LOGGER.debug(
                    "UTL Solar: fetched %d entries for %d-%02d",
                    len(monthly),
                    year,
                    month,
                )
            except Exception as err:
                _LOGGER.warning("UTL Solar: failed to fetch %d-%02d: %s", year, month, err)
                monthly = []

            for entry in sorted(monthly, key=lambda x: x.get("date", 0)):
                day = entry.get("date")
                production = entry.get("PvProduction")
                if day is None or production is None:
                    continue

                try:
                    day_int = int(day)
                    day_date = datetime(year, month, day_int).date()
                except (ValueError, TypeError):
                    continue

                if day_date < start_date or day_date > end_date:
                    continue

                cumulative += float(production)
                day_start = datetime(
                    year,
                    month,
                    day_int,
                    0,
                    0,
                    0,
                    tzinfo=dt_util.DEFAULT_TIME_ZONE,
                )
                stats.append(
                    StatisticData(
                        start=day_start,
                        state=float(production),
                        sum=cumulative,
                    )
                )

            if month == 12:
                current = current.replace(year=year + 1, month=1)
            else:
                current = current.replace(month=month + 1)

        if not stats:
            _LOGGER.warning("UTL Solar: no historical data found to import")
            return

        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name="UTL Solar Daily Production",
            source=DOMAIN,
            statistic_id=STATISTIC_ID,
            unit_of_measurement="kWh",
        )

        async_add_external_statistics(self.hass, metadata, stats)
        _LOGGER.info(
            "UTL Solar: imported %d days of history (%.2f kWh cumulative total)",
            len(stats),
            cumulative,
        )
