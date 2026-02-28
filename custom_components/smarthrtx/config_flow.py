"""Config Flow for SmartHRTX.

ADRs implemented in this module:
- ADR-002: Explicit weather entity selection (weather_entity selector)
- ADR-010: Dynamic configurable inputs (multi-step ConfigFlow)
- ADR-011: Calculation robustness (input validation)
- ADR-032: Reinforced validation (entity existence, time sequence)
"""

import logging
from typing import Any
from datetime import time as dt_time
import copy
from collections.abc import Mapping

from homeassistant.core import callback
from homeassistant.config_entries import ConfigFlow, OptionsFlow, ConfigEntry
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN

import voluptuous as vol

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_TARGET_HOUR,
    CONF_RECOVERYCALC_HOUR,
    CONF_SENSOR_INTERIOR_TEMP,
    CONF_WEATHER_ENTITY,
    CONF_TSP,
    CONF_TEMP_UNIT,
    TEMP_UNIT_CELSIUS,
    TEMP_UNIT_FAHRENHEIT,
    DEFAULT_TEMP_UNIT,
    DEFAULT_TSP,
    DEFAULT_TSP_MIN,
    DEFAULT_TSP_MAX,
    DEFAULT_TSP_STEP,
    DEFAULT_TSP_F,
    DEFAULT_TSP_MIN_F,
    DEFAULT_TSP_MAX_F,
    DEFAULT_TSP_STEP_F,
)

_LOGGER = logging.getLogger(__name__)


def _build_tsp_selector(temp_unit: str) -> selector.NumberSelector:
    """Build a NumberSelector for the Set Point in the given temperature unit."""
    if temp_unit == TEMP_UNIT_FAHRENHEIT:
        return selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=DEFAULT_TSP_MIN_F,
                max=DEFAULT_TSP_MAX_F,
                step=DEFAULT_TSP_STEP_F,
                unit_of_measurement=TEMP_UNIT_FAHRENHEIT,
                mode=selector.NumberSelectorMode.BOX,
            )
        )
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=DEFAULT_TSP_MIN,
            max=DEFAULT_TSP_MAX,
            step=DEFAULT_TSP_STEP,
            unit_of_measurement=TEMP_UNIT_CELSIUS,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def _tsp_to_celsius(tsp: float, temp_unit: str) -> float:
    """Convert a Set Point value to Celsius for internal storage."""
    if temp_unit == TEMP_UNIT_FAHRENHEIT:
        return (tsp - 32) * 5 / 9
    return tsp


def _tsp_from_celsius(tsp_celsius: float, temp_unit: str) -> float:
    """Convert a stored Celsius Set Point to the display unit."""
    if temp_unit == TEMP_UNIT_FAHRENHEIT:
        return round(tsp_celsius * 9 / 5 + 32, 1)
    return tsp_celsius


def add_suggested_values_to_schema(
    data_schema: vol.Schema, suggested_values: Mapping[str, Any]
) -> vol.Schema:
    """Make a copy of the schema, populated with suggested values.

    For each schema marker matching items in `suggested_values`,
    the `suggested_value` will be set. The existing `suggested_value` will
    be left untouched if there is no matching item.
    """
    schema = {}
    for key, val in data_schema.schema.items():
        new_key = key
        if key in suggested_values and isinstance(key, vol.Marker):
            # Copy the marker to not modify the flow schema
            new_key = copy.copy(key)
            new_key.description = {
                "suggested_value": suggested_values[key]
            }  # type: ignore
        schema[new_key] = val
    _LOGGER.debug("add_suggested_values_to_schema: schema=%s", schema)
    return vol.Schema(schema)


class SmartHRTConfigFlow(ConfigFlow, domain=DOMAIN):
    """La classe qui implémente le config flow pour SmartHRTX.
    Elle doit dériver de ConfigFlow"""

    # La version de notre configFlow. Va permettre de migrer les entités
    # vers une version plus récente en cas de changement
    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._user_inputs: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        """Get options flow for this handler"""
        return SmartHRTOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Gestion de l'étape 'user'. Point d'entrée du configFlow.
        Demande le nom de l'intégration.
        """
        user_form = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
            }
        )

        if user_input is None:
            _LOGGER.debug(
                "config_flow step user (1). First call: no user_input -> showing user_form"
            )
            return self.async_show_form(
                step_id="user",
                data_schema=add_suggested_values_to_schema(
                    data_schema=user_form, suggested_values=self._user_inputs
                ),
            )  # pyright: ignore[reportReturnType]

        # Second call: user_input received -> store the result
        _LOGGER.debug(
            "config_flow step user (2). Received values: %s", user_input
        )
        # Store user_input
        self._user_inputs.update(user_input)

        # Check for duplicate entries based on name
        await self.async_set_unique_id(user_input[CONF_NAME])
        self._abort_if_unique_id_configured()

        # Proceed to step 2 (sensor configuration)
        return await self.async_step_sensors()

    async def async_step_sensors(self, user_input: dict | None = None) -> FlowResult:
        """Handle the sensors step. Configure sensors and parameters."""
        errors: dict[str, str] = {}

        # Determine the display unit for building the form schema
        display_unit = (
            user_input.get(CONF_TEMP_UNIT, DEFAULT_TEMP_UNIT)
            if user_input is not None
            else self._user_inputs.get(CONF_TEMP_UNIT, DEFAULT_TEMP_UNIT)
        )
        tsp_default = DEFAULT_TSP_F if display_unit == TEMP_UNIT_FAHRENHEIT else DEFAULT_TSP

        sensors_form = vol.Schema(
            {
                vol.Required(CONF_TARGET_HOUR): selector.TimeSelector(),
                vol.Required(
                    CONF_RECOVERYCALC_HOUR, default="23:00:00"
                ): selector.TimeSelector(),
                vol.Required(CONF_SENSOR_INTERIOR_TEMP): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=SENSOR_DOMAIN),
                ),
                # ADR-002: Explicit weather entity selection
                vol.Required(CONF_WEATHER_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="weather"),
                ),
                # Temperature unit preference for Set Point input
                vol.Required(
                    CONF_TEMP_UNIT, default=DEFAULT_TEMP_UNIT
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[TEMP_UNIT_CELSIUS, TEMP_UNIT_FAHRENHEIT],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                # Set Point in the chosen unit (stored internally in Celsius)
                vol.Required(CONF_TSP, default=tsp_default): _build_tsp_selector(display_unit),
            }
        )

        if user_input is None:
            _LOGGER.debug(
                "config_flow step sensors (1). First call: no user_input -> showing sensors_form"
            )
            # Convert stored Celsius TSP to display unit for pre-filling
            suggested = dict(self._user_inputs)
            if CONF_TSP in suggested:
                suggested[CONF_TSP] = _tsp_from_celsius(suggested[CONF_TSP], display_unit)
            return self.async_show_form(
                step_id="sensors",
                data_schema=add_suggested_values_to_schema(
                    data_schema=sensors_form, suggested_values=suggested
                ),
            )  # pyright: ignore[reportReturnType]

        # Second call: validate inputs (ADR-032)
        _LOGGER.debug("config_flow step sensors (2). Received values: %s", user_input)

        temp_unit = user_input.get(CONF_TEMP_UNIT, DEFAULT_TEMP_UNIT)
        tsp_raw = user_input.get(CONF_TSP, DEFAULT_TSP)
        tsp_celsius = _tsp_to_celsius(tsp_raw, temp_unit)

        # ADR-032: Validate weather entity
        weather_entity_id = user_input.get(CONF_WEATHER_ENTITY)
        if weather_entity_id:
            weather_state = self.hass.states.get(weather_entity_id)
            if weather_state is None:
                errors[CONF_WEATHER_ENTITY] = "weather_not_found"
            elif not self._is_valid_weather_entity(weather_state):
                errors[CONF_WEATHER_ENTITY] = "weather_incompatible"

        # ADR-032: Validate interior temperature sensor
        temp_sensor_id = user_input.get(CONF_SENSOR_INTERIOR_TEMP)
        if temp_sensor_id:
            temp_state = self.hass.states.get(temp_sensor_id)
            if temp_state is None:
                errors[CONF_SENSOR_INTERIOR_TEMP] = "sensor_not_found"

        # ADR-032: Validate Set Point (always checked in Celsius)
        if not (DEFAULT_TSP_MIN <= tsp_celsius <= DEFAULT_TSP_MAX):
            errors[CONF_TSP] = "tsp_out_of_range"

        # ADR-032: Validate time sequence
        target_hour = user_input.get(CONF_TARGET_HOUR)
        recoverycalc_hour = user_input.get(CONF_RECOVERYCALC_HOUR)
        if target_hour and recoverycalc_hour:
            if not self._validate_time_sequence(recoverycalc_hour, target_hour):
                errors["base"] = "invalid_time_sequence"

        # If errors, redisplay with original user values (TSP still in user's unit)
        if errors:
            _LOGGER.debug("Config flow validation errors: %s", errors)
            return self.async_show_form(
                step_id="sensors",
                data_schema=add_suggested_values_to_schema(
                    data_schema=sensors_form, suggested_values=user_input
                ),
                errors=errors,
            )  # pyright: ignore[reportReturnType]

        # Store TSP converted to Celsius; keep unit preference for options flow
        user_input[CONF_TSP] = tsp_celsius
        self._user_inputs.update(user_input)
        _LOGGER.info(
            "config_flow step sensors (2). Full configuration: %s",
            self._user_inputs,
        )

        return self.async_create_entry(
            title=self._user_inputs[CONF_NAME], data=self._user_inputs
        )  # pyright: ignore[reportReturnType]

    def _is_valid_weather_entity(self, state) -> bool:
        """Check that the weather entity is valid (ADR-032).

        A valid weather entity must be in the 'weather' domain and
        ideally support forecasts.
        """
        if state is None:
            return False
        # Domain is checked by the selector, but we verify anyway
        return state.domain == "weather"

    def _validate_time_sequence(self, recoverycalc: str, target: str) -> bool:
        """Verify that recoverycalc_hour precedes target_hour (ADR-032).

        Logic: recoverycalc (23:00) should be in the evening, target (06:00) in the morning.
        If recoverycalc < target on the same day (e.g. 05:00 and 08:00),
        that is likely a configuration error.

        Args:
            recoverycalc: Heating stop hour (HH:MM:SS format)
            target: Wake-up target hour (HH:MM:SS format)

        Returns:
            True if the sequence is valid, False otherwise.
        """
        try:
            rc_parts = recoverycalc.split(":")
            tg_parts = target.split(":")
            rc_minutes = int(rc_parts[0]) * 60 + int(
                rc_parts[1] if len(rc_parts) > 1 else 0
            )
            tg_minutes = int(tg_parts[0]) * 60 + int(
                tg_parts[1] if len(tg_parts) > 1 else 0
            )

            # Valid cases:
            # 1. recoverycalc (23:00) > target (06:00) - implicit midnight crossing
            # 2. target is early morning (before noon) - always OK
            if rc_minutes > tg_minutes:
                return True  # Midnight crossing
            if tg_minutes < 12 * 60:
                return True  # Target in the morning

            # Invalid: recoverycalc and target both in the afternoon, rc < tg
            return False
        except (ValueError, IndexError):
            return True  # On parsing error, allow through


# Keys stored in 'data' (static configuration - does not change)
STATIC_KEYS = {
    CONF_NAME,
    CONF_SENSOR_INTERIOR_TEMP,
    CONF_WEATHER_ENTITY,
}
# Keys stored in 'options' (dynamic settings - modifiable without reload)
DYNAMIC_KEYS = {CONF_TARGET_HOUR, CONF_RECOVERYCALC_HOUR, CONF_TSP, CONF_TEMP_UNIT}


class SmartHRTOptionsFlow(OptionsFlow):
    """Implements the options flow for SmartHRTX.
    Must derive from OptionsFlow.

    Dynamic settings are stored in 'options' to allow
    modification without a full integration reload.
    """

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow with the existing ConfigEntry."""
        super().__init__()
        self._config_entry = config_entry
        # Initialize user_inputs by merging data and options;
        # options take priority over data for dynamic keys
        self._user_inputs: dict[str, Any] = {
            **config_entry.data,
            **config_entry.options,
        }

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        """Handle the 'init' step. Entry point of the options flow."""
        # Determine display unit (from submitted input or stored preference)
        display_unit = (
            user_input.get(CONF_TEMP_UNIT, DEFAULT_TEMP_UNIT)
            if user_input is not None
            else self._user_inputs.get(CONF_TEMP_UNIT, DEFAULT_TEMP_UNIT)
        )
        tsp_default = DEFAULT_TSP_F if display_unit == TEMP_UNIT_FAHRENHEIT else DEFAULT_TSP

        option_form = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_TARGET_HOUR): selector.TimeSelector(),
                vol.Required(
                    CONF_RECOVERYCALC_HOUR, default="23:00:00"
                ): selector.TimeSelector(),
                vol.Required(CONF_SENSOR_INTERIOR_TEMP): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=SENSOR_DOMAIN)
                ),
                # ADR-002: Explicit weather entity selection
                vol.Required(CONF_WEATHER_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="weather")
                ),
                # Temperature unit preference for Set Point input
                vol.Required(
                    CONF_TEMP_UNIT, default=DEFAULT_TEMP_UNIT
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[TEMP_UNIT_CELSIUS, TEMP_UNIT_FAHRENHEIT],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                # Set Point in the chosen unit (stored internally in Celsius)
                vol.Required(CONF_TSP, default=tsp_default): _build_tsp_selector(display_unit),
            }
        )

        if user_input is None:
            _LOGGER.debug(
                "option_flow step user (1). First call: no user_input -> showing option_form"
            )
            # Convert stored Celsius TSP to display unit for pre-filling
            suggested = dict(self._user_inputs)
            if CONF_TSP in suggested:
                suggested[CONF_TSP] = _tsp_from_celsius(suggested[CONF_TSP], display_unit)
            return self.async_show_form(
                step_id="init",
                data_schema=add_suggested_values_to_schema(
                    data_schema=option_form, suggested_values=suggested
                ),
            )  # pyright: ignore[reportReturnType]

        # Second call: user_input received -> convert TSP and store
        _LOGGER.debug(
            "option_flow step user (2). Received values: %s", user_input
        )
        temp_unit = user_input.get(CONF_TEMP_UNIT, DEFAULT_TEMP_UNIT)
        tsp_raw = user_input.get(CONF_TSP, DEFAULT_TSP)
        user_input[CONF_TSP] = _tsp_to_celsius(tsp_raw, temp_unit)
        self._user_inputs.update(user_input)

        # Proceed to finalization
        return await self.async_end()  # pyright: ignore[reportReturnType]

    async def async_end(self) -> FlowResult:
        """Finalize the ConfigEntry modification.

        Splits data into:
        - data: static configuration (sensors, name, weather)
        - options: dynamic settings (times, set point)

        Static data requires an integration reload.
        Dynamic options can be applied without a reload.
        """
        # Extract static data (requires reload)
        new_data = {
            key: self._user_inputs[key]
            for key in STATIC_KEYS
            if key in self._user_inputs
        }

        # Extract dynamic options
        new_options = {
            key: self._user_inputs[key]
            for key in DYNAMIC_KEYS
            if key in self._user_inputs
        }

        _LOGGER.info(
            "Updating entry %s. New data: %s, New options: %s",
            self._config_entry.entry_id,
            new_data,
            new_options,
        )

        # Update static data if changed
        if new_data != dict(self._config_entry.data):
            self.hass.config_entries.async_update_entry(
                self._config_entry,
                data=new_data,
            )
            _LOGGER.info("Static data updated, integration reload required")

        # Retourne les nouvelles options - Home Assistant les stockera automatiquement
        # dans config_entry.options et déclenchera update_listener
        return self.async_create_entry(title="", data=new_options)
