"""Constants for the UTL Solar integration."""

DOMAIN = "utl_solar"

API_BASE_URL = "https://utlsolarrms.com"
API_LOGIN = "/api/auth/login"
API_DEVICES = "/api/devices"
API_PLANT = "/api/plant"
API_PLANT_STATUS = "/api/plantStatus"
API_DEVICE_DAILY_CHART = "/api/charts/devices/daily/device_daily_chart"
API_PLANT_DAILY_CHART = "/api/charts/solar_power_per_plant/daily"
API_PLANT_MONTHLY_CHART = "/api/charts/solar_power_per_plant/monthly"
API_PLANT_YEARLY_CHART = "/api/charts/solar_power_per_plant/yearly"
API_PLANT_TOTAL_CHART = "/api/charts/solar_power_per_plant/total"

DEFAULT_SCAN_INTERVAL = 300  # seconds
DEFAULT_DEVICE_ID = "homeassistant-utl"
