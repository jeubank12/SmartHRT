"""Constants for the SmartHRTX integration.

ADRs implemented in this module:
- ADR-041: PERSISTED_FIELDS removed, replaced by SmartHRTData.as_dict/from_dict
- ADR-051: TimerKey for centralized timer management
"""

from enum import StrEnum

from homeassistant.const import Platform


class TimerKey(StrEnum):
    """Keys for timers managed by the system (ADR-051).

    Used with TimerManager to uniquely identify timers.
    """

    RECOVERYCALC_HOUR = "recoverycalc_hour"
    TARGET_HOUR = "target_hour"
    RECOVERY_START = "recovery_start"
    RECOVERY_UPDATE = "recovery_update"


DOMAIN = "smarthrtx"
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.TIME,
    Platform.SWITCH,
]

# Configuration keys
CONF_NAME = "name"
CONF_DEVICE_ID = "device_id"
CONF_TARGET_HOUR = "target_hour"
CONF_RECOVERYCALC_HOUR = "recoverycalc_hour"
CONF_SENSOR_INTERIOR_TEMP = "sensor_interior_temperature"
CONF_WEATHER_ENTITY = "weather_entity"
CONF_TSP = "tsp"
CONF_TEMP_UNIT = "temp_unit"  # UI temperature unit preference for config form
CONF_SENSOR_OUTDOOR_TEMP = "sensor_outdoor_temperature"
CONF_SENSOR_WIND_SPEED = "sensor_wind_speed"

# Temperature unit options for the config form
TEMP_UNIT_CELSIUS = "°C"
TEMP_UNIT_FAHRENHEIT = "°F"
DEFAULT_TEMP_UNIT = TEMP_UNIT_CELSIUS

# Default values (internal storage always in Celsius)
DEFAULT_TSP = 19.0
DEFAULT_TSP_MIN = 13.0
DEFAULT_TSP_MAX = 26.0
DEFAULT_TSP_STEP = 0.1

# Equivalent Set Point limits in Fahrenheit for the config form
DEFAULT_TSP_MIN_F = 55.0   # ≈ 13 °C
DEFAULT_TSP_MAX_F = 79.0   # ≈ 26 °C
DEFAULT_TSP_STEP_F = 0.5
DEFAULT_TSP_F = 66.0       # ≈ 19 °C

# Thermal coefficients defaults
DEFAULT_RCTH = 50.0
DEFAULT_RPTH = 50.0
DEFAULT_RCTH_MIN = 0.0
DEFAULT_RCTH_MAX = 19999.0
DEFAULT_RPTH_MIN = 0.0
DEFAULT_RPTH_MAX = 19999.0
DEFAULT_RELAXATION_FACTOR = 2.0

# ADR-007: Weather compensation - wind thresholds for interpolation
# WIND_LOW: low wind (uses rcth_lw), WIND_HIGH: high wind (uses rcth_hw)
WIND_HIGH = 60.0
WIND_LOW = 10.0

# Device info
DEVICE_MANUFACTURER = "SmartHRTX"

# Data keys for hass.data[DOMAIN][entry_id]
DATA_COORDINATOR = "coordinator"

# ADR-043: Services essentiels uniquement
# Services simplifiés
SERVICE_START_HEATING_CYCLE = "start_heating_cycle"
SERVICE_STOP_HEATING = "stop_heating"
SERVICE_START_RECOVERY = "start_recovery"
SERVICE_END_RECOVERY = "end_recovery"
SERVICE_GET_STATE = "get_state"

# Services utilitaires
SERVICE_RESET_LEARNING = "reset_learning"
SERVICE_TRIGGER_CALCULATION = "trigger_calculation"

# Weather forecast settings
FORECAST_HOURS = 3

# ADR-008: Stop validation via lag detection
# Temperature drop threshold to confirm that heating has actually stopped
TEMP_DECREASE_THRESHOLD = 0.2  # °C

# Default recoverycalc hour (23:00)
DEFAULT_RECOVERYCALC_HOUR = "23:00:00"

# ADR-041: PERSISTED_FIELDS removed
# Serialization is now centralized in SmartHRTData.as_dict/from_dict
# See coordinator.py for _PERSISTENT_FIELDS and the migration logic
