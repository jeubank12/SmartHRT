"""Package initialization for the SmartHRTX integration.

ADRs implemented in this module:
- ADR-001: Global architecture (setup/async_unload_entry)
- ADR-012: Expose entities for Lovelace (forward_entry_setups)
- ADR-016: Cleanup of obsolete time entities
- ADR-045: Pydantic runtime validation for configuration
"""

import logging

from pydantic import ValidationError

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry as er

from .const import (
    DOMAIN,
    PLATFORMS,
    DATA_COORDINATOR,
    CONF_TARGET_HOUR,
    CONF_RECOVERYCALC_HOUR,
    CONF_TSP,
    CONF_NAME,
    CONF_SENSOR_INTERIOR_TEMP,
    CONF_WEATHER_ENTITY,
    DEFAULT_TSP,
)
from .coordinator import SmartHRTCoordinator
from .services import async_setup_services, async_unload_services
from .models import ConfigFlowDataModel

_LOGGER = logging.getLogger(__name__)

# Configuration schema version
CONFIG_ENTRY_VERSION = 1


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry to current version.

    Called by Home Assistant when the config entry version differs from
    CONFIG_ENTRY_VERSION.
    """
    _LOGGER.debug(
        "Migrating SmartHRTX config entry from version %s to %s",
        entry.version,
        CONFIG_ENTRY_VERSION,
    )

    if entry.version > CONFIG_ENTRY_VERSION:
        # Downgrade not supported
        _LOGGER.error(
            "Cannot downgrade SmartHRTX config entry from version %s to %s",
            entry.version,
            CONFIG_ENTRY_VERSION,
        )
        return False

    # Example of a future migration:
    # if entry.version == 1:
    #     new_data = {**entry.data, "new_field": "default_value"}
    #     hass.config_entries.async_update_entry(entry, data=new_data, version=2)

    return True


async def _remove_obsolete_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove obsolete entities from the registry (ADR-016).

    The read-only time entities (recoverystart_hour, recoveryupdate_hour)
    were removed and replaced by timestamp sensors.
    The recovery_start_sensor (text) was removed as redundant.
    The target_hour and recoverycalc_hour timestamp sensors were renamed
    to avoid unique_id conflicts with the time entities.
    This function cleans up the old entities from the registry.
    """
    entity_reg = er.async_get(hass)

    # List of obsolete entities to remove (unique_id, platform)
    obsolete_entities = [
        (f"{entry.entry_id}_recoverystart_hour", "time"),  # time.recoverystart_hour
        (f"{entry.entry_id}_recoveryupdate_hour", "time"),  # time.recoveryupdate_hour
        (
            f"{entry.entry_id}_recovery_start_sensor",
            "sensor",
        ),  # sensor with label (text)
        # Migration v1.1: timestamp sensors renamed to avoid conflict with time entities
        (
            f"{entry.entry_id}_target_hour",
            "sensor",
        ),  # old timestamp sensor -> _target_hour_timestamp
        (
            f"{entry.entry_id}_recoverycalc_hour",
            "sensor",
        ),  # old timestamp sensor -> _recoverycalc_hour_timestamp
    ]

    for unique_id, platform in obsolete_entities:
        entity_id = entity_reg.async_get_entity_id(platform, DOMAIN, unique_id)
        if entity_id:
            _LOGGER.info(
                "Removing obsolete entity: %s (unique_id: %s, platform: %s)",
                entity_id,
                unique_id,
                platform,
            )
            entity_reg.async_remove(entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up entities from a config entry.

    ADR-001: Main integration entry point.
    ADR-012: Configure platforms (sensor, number, time, switch) for Lovelace.
    """

    _LOGGER.debug(
        "async_setup_entry called: entry_id='%s', data='%s'",
        entry.entry_id,
        entry.data,
    )

    hass.data.setdefault(DOMAIN, {})

    # Create coordinator
    coordinator = SmartHRTCoordinator(hass, entry)
    await coordinator.async_setup()

    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
    }

    # Register update_listener for options changes
    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Clean up obsolete entities (ADR-016)
    await _remove_obsolete_entities(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services (once for all instances)
    await async_setup_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    # Unload coordinator
    if entry.entry_id in hass.data[DOMAIN]:
        coordinator = hass.data[DOMAIN][entry.entry_id].get(DATA_COORDINATOR)
        if coordinator:
            await coordinator.async_unload()
        del hass.data[DOMAIN][entry.entry_id]

    # Unload platforms
    result = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Unregister services if this was the last instance
    await async_unload_services(hass)

    return result


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply options changes without reloading the integration.

    ADR-045: Uses Pydantic validation before applying options.

    Dynamic options (target_hour, recoverycalc_hour, tsp) can be applied
    live via the coordinator, avoiding a full reload that would reset the
    state machine.
    """
    coordinator = hass.data[DOMAIN][entry.entry_id].get(DATA_COORDINATOR)
    if not coordinator:
        _LOGGER.warning("Coordinator not found for entry %s", entry.entry_id)
        return

    options = entry.options
    _LOGGER.debug("Applying options update: %s", options)

    # ADR-045: Pydantic validation before applying
    try:
        validated = ConfigFlowDataModel(
            name=entry.data.get(CONF_NAME, "SmartHRTX"),
            target_hour=options.get(
                CONF_TARGET_HOUR,
                entry.data.get(CONF_TARGET_HOUR, "06:00:00"),
            ),
            recoverycalc_hour=options.get(
                CONF_RECOVERYCALC_HOUR,
                entry.data.get(CONF_RECOVERYCALC_HOUR, "23:00:00"),
            ),
            tsp=options.get(CONF_TSP, entry.data.get(CONF_TSP, DEFAULT_TSP)),
            sensor_interior_temperature=entry.data.get(
                CONF_SENSOR_INTERIOR_TEMP, "sensor.temperature"
            ),
            weather_entity=entry.data.get(CONF_WEATHER_ENTITY, "weather.home"),
        )
    except ValidationError as e:
        _LOGGER.error("ADR-045: Invalid configuration: %s", e)
        # Notify the user via persistent_notification
        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "SmartHRTX - Invalid configuration",
                "message": f"Validation error: {e}",
                "notification_id": "smarthrtx_config_error",
            },
        )
        return  # Do not apply invalid configuration

    # Apply only if validation succeeded
    if CONF_TSP in options:
        coordinator.set_tsp(validated.tsp)

    if CONF_TARGET_HOUR in options:
        coordinator.set_target_hour(validated.target_hour_as_time)

    if CONF_RECOVERYCALC_HOUR in options:
        coordinator.set_recoverycalc_hour(validated.recoverycalc_hour_as_time)

    _LOGGER.info(
        "ADR-045: Configuration validated and applied (tsp=%.1f, target=%s, recovery=%s)",
        validated.tsp,
        validated.target_hour,
        validated.recoverycalc_hour,
    )
