"""Implements the SmartHRT switch entities.

ADRs implemented in this module:
- ADR-003: Enable/disable the state machine (SmartHeatingSwitch)
- ADR-006: Adaptive mode for learning (AdaptiveSwitch)
- ADR-012: Expose entities for Lovelace (switches as HA entities)
- ADR-027: Use CoordinatorEntity for automatic synchronization
"""

import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo, DeviceEntryType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
    """Set up switch entities from the ConfigEntry configuration."""

    _LOGGER.debug("Calling switch async_setup_entry entry=%s", entry)

    coordinator: SmartHRTCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    entities = [
        SmartHRTSmartHeatingSwitch(coordinator, entry),
        SmartHRTAdaptiveSwitch(coordinator, entry),
    ]
    async_add_entities(entities, True)


class SmartHRTBaseSwitch(CoordinatorEntity[SmartHRTCoordinator], SwitchEntity):
    """Base class for SmartHRT switches (ADR-027: CoordinatorEntity)."""

    def __init__(
        self, coordinator: SmartHRTCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the base switch."""
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


class SmartHRTSmartHeatingSwitch(SmartHRTBaseSwitch):
    """Switch to enable/disable smart heating mode.

    ADR-003: Enables/disables the complete state machine.
    When disabled, no heating start calculation is performed.
    """

    def __init__(
        self, coordinator: SmartHRTCoordinator, config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_name = "Smart Heating Mode"
        self._attr_unique_id = f"{self._device_id}_smartheating_mode"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.smartheating_mode

    @property
    def icon(self) -> str | None:
        return "mdi:home-thermometer" if self.is_on else "mdi:home-thermometer-outline"

    async def async_turn_on(self, **kwargs) -> None:
        """Enable smart heating mode."""
        _LOGGER.info("SmartHeating mode enabled")
        self.coordinator.set_smartheating_mode(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable smart heating mode."""
        _LOGGER.info("SmartHeating mode disabled")
        self.coordinator.set_smartheating_mode(False)


class SmartHRTAdaptiveSwitch(SmartHRTBaseSwitch):
    """Switch to enable/disable adaptive mode (auto-calibration).

    ADR-006: Enables/disables continuous learning of thermal coefficients.
    When enabled, RCth/RPth are updated after each heating cycle.
    """

    def __init__(
        self, coordinator: SmartHRTCoordinator, config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_name = "Adaptive Mode"
        self._attr_unique_id = f"{self._device_id}_adaptive_mode"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.recovery_adaptive_mode

    @property
    def icon(self) -> str | None:
        return "mdi:brain" if self.is_on else "mdi:brain-off-outline"

    async def async_turn_on(self, **kwargs) -> None:
        """Enable adaptive mode."""
        _LOGGER.info("Adaptive mode enabled")
        self.coordinator.set_adaptive_mode(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable adaptive mode."""
        _LOGGER.info("Adaptive mode disabled")
        self.coordinator.set_adaptive_mode(False)
