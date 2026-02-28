"""Implements the SmartHRT time entities.

ADRs implemented in this module:
- ADR-012: Expose entities for Lovelace (time as HA entities)
- ADR-014: Format dates in local timezone (dt_util.as_local())
- ADR-027: Use CoordinatorEntity for automatic synchronization
"""

import logging
from datetime import time as dt_time

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.time import TimeEntity
from homeassistant.helpers.device_registry import DeviceInfo, DeviceEntryType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    DEVICE_MANUFACTURER,
    CONF_NAME,
    DATA_COORDINATOR,
)
from .coordinator import SmartHRTCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up time entities from the ConfigEntry configuration."""

    _LOGGER.debug("Calling time async_setup_entry entry=%s", entry)

    coordinator: SmartHRTCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    entities = [
        SmartHRTTargetHourTime(coordinator, entry),
        SmartHRTRecoveryCalcHourTime(coordinator, entry),
        SmartHRTRecoveryStartTime(coordinator, entry),
    ]
    async_add_entities(entities, True)


class SmartHRTBaseTime(CoordinatorEntity[SmartHRTCoordinator], TimeEntity):
    """Base class for SmartHRT time entities (ADR-027: CoordinatorEntity)."""

    def __init__(
        self, coordinator: SmartHRTCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the entity."""
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


class SmartHRTTargetHourTime(SmartHRTBaseTime):
    """Time entity for the wake-up hour."""

    def __init__(
        self, coordinator: SmartHRTCoordinator, config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_name = "Wake-up Hour"
        self._attr_unique_id = f"{self._device_id}_target_hour"

    @property
    def native_value(self) -> dt_time:
        """Return the wake-up hour from the coordinator."""
        return self.coordinator.data.target_hour

    @property
    def icon(self) -> str | None:
        return "mdi:clock-end"

    async def async_set_value(self, value: dt_time) -> None:
        """Update the wake-up hour."""
        _LOGGER.info("Target hour changed to: %s", value)
        self.coordinator.set_target_hour(value)


class SmartHRTRecoveryCalcHourTime(SmartHRTBaseTime):
    """Time entity for the heating stop hour (evening)."""

    def __init__(
        self, coordinator: SmartHRTCoordinator, config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_name = "Heating Stop Hour"
        self._attr_unique_id = f"{self._device_id}_recoverycalc_hour"

    @property
    def native_value(self) -> dt_time:
        """Return the heating stop hour from the coordinator."""
        return self.coordinator.data.recoverycalc_hour

    @property
    def icon(self) -> str | None:
        return "mdi:clock-in"

    async def async_set_value(self, value: dt_time) -> None:
        """Update the heating stop hour."""
        _LOGGER.info("Recovery calc hour changed to: %s", value)
        self.coordinator.set_recoverycalc_hour(value)


class SmartHRTRecoveryStartTime(SmartHRTBaseTime):
    """Time entity for the heating start hour (read-only, calculated automatically)."""

    def __init__(
        self, coordinator: SmartHRTCoordinator, config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_name = "Heating Start Hour"
        self._attr_unique_id = f"{self._device_id}_recovery_start_time"

    @property
    def native_value(self) -> dt_time | None:
        """Return the heating start hour from the coordinator."""
        if self.coordinator.data.recovery_start_hour:
            local_time = dt_util.as_local(self.coordinator.data.recovery_start_hour)
            return local_time.time()
        return None

    @property
    def icon(self) -> str | None:
        return "mdi:radiator"

    async def async_set_value(self, value: dt_time) -> None:
        """This entity is read-only (calculated automatically)."""
        _LOGGER.warning(
            "SmartHRT Recovery Start time is read-only and calculated automatically"
        )
