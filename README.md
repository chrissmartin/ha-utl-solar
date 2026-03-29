# UTL Solar Inverter Home Assistant Integration

[![HACS Validation](https://github.com/chrissmartin/ha-utl-solar/actions/workflows/validate.yml/badge.svg)](https://github.com/chrissmartin/ha-utl-solar/actions/workflows/validate.yml)

Home Assistant integration for [UTL Solar RMS](https://utlsolarrms.com) — monitor your UTL solar inverter directly from Home Assistant using the same API as the UTL Solar SUN+ app.

## Features

- Real-time solar power monitoring
- Daily energy production tracking
- AC and DC electrical readings (voltage, current, power)
- Grid connection status
- Historical production data sync into Home Assistant statistics

### Sensors

| Sensor              | Unit | Description                            |
| ------------------- | ---- | -------------------------------------- |
| Solar power         | kW   | Current solar power output             |
| Daily production    | kWh  | Total energy produced today            |
| Peak hours today    | h    | Equivalent peak sun hours              |
| Power normalized    | %    | Power output as percentage of capacity |
| Grid status         | —    | On-grid connection status              |
| Grid voltage        | V    | AC grid voltage                        |
| Grid current        | A    | AC grid current                        |
| AC output power     | kW   | AC output power                        |
| PV string 1 voltage | V    | DC input voltage                       |
| PV string 1 current | A    | DC input current                       |
| DC input power      | kW   | DC input power                         |

### Button

| Entity       | Description                                                                       |
| ------------ | --------------------------------------------------------------------------------- |
| Sync history | Imports historical daily production data into Home Assistant long-term statistics |

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click the three dots menu in the top right and select **Custom repositories**
3. Add `https://github.com/chrissmartin/ha-utl-solar` with category **Integration**
4. Search for "UTL Solar" and install it
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/utl_solar` directory to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** > **Devices & Services** > **Add Integration**
2. Search for **UTL Solar**
3. Enter your UTL Solar SUN+ app email and password
4. The integration will validate your credentials and set up the sensors

## Data Refresh

The integration polls the UTL Solar RMS API every 5 minutes for updated readings.

## Support

If you find this integration useful, consider supporting the project:

<a href="https://www.buymeacoffee.com/chrissmartin" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174"></a>
