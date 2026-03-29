"""Sensor platform for UTL Solar."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import UTLSolarConfigEntry
from .const import DOMAIN
from .coordinator import UTLSolarCoordinator


@dataclass(frozen=True, kw_only=True)
class UTLSolarSensorEntityDescription(SensorEntityDescription):
    """Describes a UTL Solar sensor entity."""

    source: str


SENSOR_DESCRIPTIONS: tuple[UTLSolarSensorEntityDescription, ...] = (
    UTLSolarSensorEntityDescription(
        key="solar_power",
        translation_key="solar_power",
        source="inverter",
        native_unit_of_measurement="kW",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    UTLSolarSensorEntityDescription(
        key="daily_production",
        translation_key="daily_production",
        source="inverter",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    UTLSolarSensorEntityDescription(
        key="peak_hours_today",
        translation_key="peak_hours_today",
        source="inverter",
        native_unit_of_measurement="h",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    UTLSolarSensorEntityDescription(
        key="power_normalized",
        translation_key="power_normalized",
        source="inverter",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    UTLSolarSensorEntityDescription(
        key="on_grid_status",
        translation_key="on_grid_status",
        source="plant",
    ),
    UTLSolarSensorEntityDescription(
        key="ac_voltage_a",
        translation_key="ac_voltage_a",
        source="realtime",
        native_unit_of_measurement="V",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    UTLSolarSensorEntityDescription(
        key="ac_current_a",
        translation_key="ac_current_a",
        source="realtime",
        native_unit_of_measurement="A",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    UTLSolarSensorEntityDescription(
        key="ac_power_a",
        translation_key="ac_power_a",
        source="realtime",
        native_unit_of_measurement="kW",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    UTLSolarSensorEntityDescription(
        key="dc_voltage_1",
        translation_key="dc_voltage_1",
        source="realtime",
        native_unit_of_measurement="V",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    UTLSolarSensorEntityDescription(
        key="dc_current_1",
        translation_key="dc_current_1",
        source="realtime",
        native_unit_of_measurement="A",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    UTLSolarSensorEntityDescription(
        key="dc_power_1",
        translation_key="dc_power_1",
        source="realtime",
        native_unit_of_measurement="kW",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UTLSolarConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up UTL Solar sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        UTLSolarSensor(coordinator, entry, description) for description in SENSOR_DESCRIPTIONS
    )


class UTLSolarSensor(CoordinatorEntity[UTLSolarCoordinator], SensorEntity):
    """Representation of a UTL Solar sensor."""

    entity_description: UTLSolarSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: UTLSolarCoordinator,
        entry: UTLSolarConfigEntry,
        description: UTLSolarSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

        inverter = coordinator.data.get("inverter", {}) if coordinator.data else {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="UTL Solar Inverter",
            manufacturer="UTL",
            model=inverter.get("device_type", "Solar Inverter"),
            serial_number=inverter.get("inverter_sno", "unknown"),
        )

    @property
    def native_value(self) -> float | str | None:
        """Return the sensor value."""
        if not self.coordinator.data:
            return None
        source_data = self.coordinator.data.get(self.entity_description.source, {})
        value = source_data.get(self.entity_description.key)
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return value
