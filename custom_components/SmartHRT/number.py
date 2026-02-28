"""Implements the SmartHRT number entities.

ADRs implemented in this module:
- ADR-006: Continuous learning (SmartHRTRelaxationNumber for the factor)
- ADR-007: Weather compensation (RCth/RPth LW/HW for wind interpolation)
- ADR-012: Expose entities for Lovelace (numbers as HA entities)
- ADR-027: Use CoordinatorEntity for automatic synchronization
"""

import logging

from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.device_registry import DeviceInfo, DeviceEntryType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    DEVICE_MANUFACTURER,
    CONF_NAME,
    DATA_COORDINATOR,
    DEFAULT_TSP_MIN,
    DEFAULT_TSP_MAX,
    DEFAULT_TSP_STEP,
    DEFAULT_RCTH_MIN,
    DEFAULT_RCTH_MAX,
    DEFAULT_RPTH_MIN,
    DEFAULT_RPTH_MAX,
)
from .coordinator import SmartHRTCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up number entities from the ConfigEntry configuration."""

    _LOGGER.debug("Calling number async_setup_entry entry=%s", entry)

    coordinator: SmartHRTCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    entities = [
        SmartHRTSetPointNumber(coordinator, entry),
        SmartHRTRCthNumber(coordinator, entry),
        SmartHRTRPthNumber(coordinator, entry),
        SmartHRTRCthLWNumber(coordinator, entry),
        SmartHRTRCthHWNumber(coordinator, entry),
        SmartHRTRPthLWNumber(coordinator, entry),
        SmartHRTRPthHWNumber(coordinator, entry),
        SmartHRTRelaxationNumber(coordinator, entry),
    ]
    async_add_entities(entities, True)


class SmartHRTBaseNumber(CoordinatorEntity[SmartHRTCoordinator], NumberEntity):
    """Base class for SmartHRT number entities (ADR-027: CoordinatorEntity)."""

    def __init__(
        self, coordinator: SmartHRTCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the base number entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._device_id = config_entry.entry_id
        self._device_name = config_entry.data.get(CONF_NAME, "SmartHRT")
        self._attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_name,
            manufacturer=DEVICE_MANUFACTURER,
            model="Smart Heating Regulator",
        )


class SmartHRTSetPointNumber(SmartHRTBaseNumber):
    """Number entity for the temperature set point."""

    def __init__(
        self, coordinator: SmartHRTCoordinator, config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_name = "Set Point"
        self._attr_unique_id = f"{self._device_id}_setpoint"
        self._attr_native_min_value = DEFAULT_TSP_MIN
        self._attr_native_max_value = DEFAULT_TSP_MAX
        self._attr_native_step = DEFAULT_TSP_STEP
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_mode = NumberMode.BOX

    @property
    def native_value(self) -> float:
        return self.coordinator.data.tsp

    @property
    def icon(self) -> str | None:
        return "mdi:thermometer"

    async def async_set_native_value(self, value: float) -> None:
        """Update the set point value."""
        _LOGGER.info("Set point changed to: %s", value)
        self.coordinator.set_tsp(value)


class SmartHRTRCthNumber(SmartHRTBaseNumber):
    """Number entity for RCth (thermal cooling constant)."""

    def __init__(
        self, coordinator: SmartHRTCoordinator, config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_name = "RCth"
        self._attr_unique_id = f"{self._device_id}_rcth"
        self._attr_native_min_value = DEFAULT_RCTH_MIN
        self._attr_native_max_value = DEFAULT_RCTH_MAX
        self._attr_native_step = 0.5
        self._attr_native_unit_of_measurement = UnitOfTime.HOURS
        self._attr_mode = NumberMode.BOX

    @property
    def native_value(self) -> float:
        return round(self.coordinator.data.rcth, 2)

    @property
    def icon(self) -> str | None:
        return "mdi:home-battery-outline"

    async def async_set_native_value(self, value: float) -> None:
        _LOGGER.info("RCth changed to: %s", value)
        self.coordinator.set_rcth(value)


class SmartHRTRPthNumber(SmartHRTBaseNumber):
    """Number entity for RPth (thermal heating power constant)."""

    def __init__(
        self, coordinator: SmartHRTCoordinator, config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_name = "RPth"
        self._attr_unique_id = f"{self._device_id}_rpth"
        self._attr_native_min_value = DEFAULT_RPTH_MIN
        self._attr_native_max_value = DEFAULT_RPTH_MAX
        self._attr_native_step = 0.5
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_mode = NumberMode.BOX

    @property
    def native_value(self) -> float:
        return round(self.coordinator.data.rpth, 2)

    @property
    def icon(self) -> str | None:
        return "mdi:home-lightning-bolt-outline"

    async def async_set_native_value(self, value: float) -> None:
        _LOGGER.info("RPth changed to: %s", value)
        self.coordinator.set_rpth(value)


class SmartHRTRCthLWNumber(SmartHRTBaseNumber):
    """Number entity for RCth low wind.

    ADR-007: Weather compensation - cooling coefficient for low wind.
    Used for linear interpolation based on wind speed.
    """

    def __init__(
        self, coordinator: SmartHRTCoordinator, config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_name = "RCth (Low Wind)"
        self._attr_unique_id = f"{self._device_id}_rcth_lw"
        self._attr_native_min_value = DEFAULT_RCTH_MIN
        self._attr_native_max_value = DEFAULT_RCTH_MAX
        self._attr_native_step = 0.5
        self._attr_native_unit_of_measurement = UnitOfTime.HOURS
        self._attr_mode = NumberMode.BOX

    @property
    def native_value(self) -> float:
        return round(self.coordinator.data.rcth_lw, 2)

    @property
    def icon(self) -> str | None:
        return "mdi:home-battery-outline"

    async def async_set_native_value(self, value: float) -> None:
        _LOGGER.info("RCth LW changed to: %s", value)
        self.coordinator.set_rcth_lw(value)


class SmartHRTRCthHWNumber(SmartHRTBaseNumber):
    """Number entity for RCth high wind."""

    def __init__(
        self, coordinator: SmartHRTCoordinator, config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_name = "RCth (High Wind)"
        self._attr_unique_id = f"{self._device_id}_rcth_hw"
        self._attr_native_min_value = DEFAULT_RCTH_MIN
        self._attr_native_max_value = DEFAULT_RCTH_MAX
        self._attr_native_step = 0.5
        self._attr_native_unit_of_measurement = UnitOfTime.HOURS
        self._attr_mode = NumberMode.BOX

    @property
    def native_value(self) -> float:
        return round(self.coordinator.data.rcth_hw, 2)

    @property
    def icon(self) -> str | None:
        return "mdi:home-battery-outline"

    async def async_set_native_value(self, value: float) -> None:
        _LOGGER.info("RCth HW changed to: %s", value)
        self.coordinator.set_rcth_hw(value)


class SmartHRTRPthLWNumber(SmartHRTBaseNumber):
    """Number entity for RPth low wind."""

    def __init__(
        self, coordinator: SmartHRTCoordinator, config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_name = "RPth (Low Wind)"
        self._attr_unique_id = f"{self._device_id}_rpth_lw"
        self._attr_native_min_value = DEFAULT_RPTH_MIN
        self._attr_native_max_value = DEFAULT_RPTH_MAX
        self._attr_native_step = 0.5
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_mode = NumberMode.BOX

    @property
    def native_value(self) -> float:
        return round(self.coordinator.data.rpth_lw, 2)

    @property
    def icon(self) -> str | None:
        return "mdi:home-lightning-bolt-outline"

    async def async_set_native_value(self, value: float) -> None:
        _LOGGER.info("RPth LW changed to: %s", value)
        self.coordinator.set_rpth_lw(value)


class SmartHRTRPthHWNumber(SmartHRTBaseNumber):
    """Number entity for RPth high wind."""

    def __init__(
        self, coordinator: SmartHRTCoordinator, config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_name = "RPth (High Wind)"
        self._attr_unique_id = f"{self._device_id}_rpth_hw"
        self._attr_native_min_value = DEFAULT_RPTH_MIN
        self._attr_native_max_value = DEFAULT_RPTH_MAX
        self._attr_native_step = 0.5
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_mode = NumberMode.BOX

    @property
    def native_value(self) -> float:
        return round(self.coordinator.data.rpth_hw, 2)

    @property
    def icon(self) -> str | None:
        return "mdi:home-lightning-bolt-outline"

    async def async_set_native_value(self, value: float) -> None:
        _LOGGER.info("RPth HW changed to: %s", value)
        self.coordinator.set_rpth_hw(value)


class SmartHRTRelaxationNumber(SmartHRTBaseNumber):
    """Number entity for the relaxation factor.

    ADR-006: Continuous learning - controls the convergence speed.
    Higher values mean slower but more stable learning.
    """

    def __init__(
        self, coordinator: SmartHRTCoordinator, config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_name = "Relaxation Factor"
        self._attr_unique_id = f"{self._device_id}_relaxation"
        self._attr_native_min_value = 0.0
        self._attr_native_max_value = 15.0
        self._attr_native_step = 0.05
        self._attr_mode = NumberMode.BOX

    @property
    def native_value(self) -> float:
        return self.coordinator.data.relaxation_factor

    @property
    def icon(self) -> str | None:
        return "mdi:brain"

    async def async_set_native_value(self, value: float) -> None:
        _LOGGER.info("Relaxation factor changed to: %s", value)
        self.coordinator.set_relaxation_factor(value)
