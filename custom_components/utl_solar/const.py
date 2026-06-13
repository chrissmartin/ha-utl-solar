"""Constants for the UTL Solar integration."""

DOMAIN = "utl_solar"

API_BASE_URL = "https://utlsolarrms.com"

# --- Endpoints consumed by this integration ---------------------------------
API_LOGIN = "/api/auth/login"
API_DEVICES = "/api/devices"
API_PLANT = "/api/plant"
API_DEVICE_DAILY_CHART = "/api/charts/devices/daily/device_daily_chart"
API_PLANT_DAILY_CHART = "/api/charts/solar_power_per_plant/daily"
API_PLANT_MONTHLY_CHART = "/api/charts/solar_power_per_plant/monthly"

# --- Known UTL Solar RMS provider endpoints (not yet consumed) --------------
# Documented here for reference so future features (yearly/total statistics,
# live plant-status polling) can adopt them without rediscovering the API.
# Kept intentionally even though unused; see issue tracker for roadmap.
API_PLANT_STATUS = "/api/plantStatus"  # current on/off-grid + alarm state
API_PLANT_YEARLY_CHART = "/api/charts/solar_power_per_plant/yearly"  # per-month totals
API_PLANT_TOTAL_CHART = "/api/charts/solar_power_per_plant/total"  # per-year totals

DEFAULT_SCAN_INTERVAL = 300  # seconds
NIGHT_SCAN_INTERVAL = 3600  # seconds (60 min)
NIGHT_START_HOUR = 19  # 7pm local time
NIGHT_END_HOUR = 6  # 6am local time
DEFAULT_DEVICE_ID = "homeassistant-utl"

# Configurable daytime poll interval (exposed via the options flow).
CONF_SCAN_INTERVAL = "scan_interval"
MIN_SCAN_INTERVAL = 60  # seconds — floor to avoid hammering the API
MAX_SCAN_INTERVAL = 3600  # seconds

# Historical-data sync pacing (the "Sync history" button).
HISTORY_SYNC_REQUEST_DELAY = 1.0  # seconds between monthly requests
HISTORY_SYNC_MAX_RETRY_AFTER = 60.0  # cap on an honored Retry-After backoff
