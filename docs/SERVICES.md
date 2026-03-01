# SmartHRTX Services

This document describes the available services to control SmartHRTX and their relationship with the state machine.

## State Machine

SmartHRTX uses an explicit state machine to model the daily thermal cycle:

```
HEATING_ON → DETECTING_LAG → MONITORING → RECOVERY → HEATING_PROCESSING → HEATING_ON
    ↓            ↓              ↓            ↓             ↓
 (State 1)    (State 2)     (State 3)    (State 4)     (State 5)
```

### State Descriptions

- **HEATING_ON**: Normal daytime heating mode
- **DETECTING_LAG**: Temperature lag detection after heating stops (-0.2°C)
- **MONITORING**: Nighttime monitoring, recurring recovery time calculations
- **RECOVERY**: Recovery start moment (RCth calculation)
- **HEATING_PROCESSING**: Temperature rise phase (RPth calculation)

## Simplified Services (Recommended)

These services are user-oriented and correspond to the natural transitions of the state machine.

### `start_heating_cycle`

**Usage**: Starts a new daily heating cycle

**Transition**: `*` → `HEATING_ON`

**Parameters**:

- `entry_id` (optional): Instance ID for multi-instance setups

**Return**:

```yaml
success: true
state: "heating_on"
message: "Heating cycle started"
```

**Example call**:

```yaml
service: smarthrtx.start_heating_cycle
```

---

### `stop_heating`

**Usage**: Stops heating and starts nighttime monitoring

**Transition**: `HEATING_ON` → `DETECTING_LAG` → `MONITORING`

**Description**:

- Records current temperatures
- Activates temperature lag detection
- Launches recovery time calculations once lag is detected

**Parameters**:

- `entry_id` (optional): Instance ID for multi-instance setups

**Return**:

```yaml
success: true
state: "monitoring"
recovery_start_hour: "2026-02-04T04:30:00+01:00"
message: "Heating stopped, monitoring started"
```

**Example call**:

```yaml
service: smarthrtx.stop_heating
```

**⚠️ Note**: This service is normally called automatically at `recoverycalc_hour` (default 11:00 PM).

---

### `start_recovery`

**Usage**: Starts the heating recovery phase

**Transition**: `MONITORING` → `RECOVERY` → `HEATING_PROCESSING`

**Description**:

- Calculates RCth (thermal time constant)
- Enables RPth calculation mode
- Automatic transition to HEATING_PROCESSING

**Parameters**:

- `entry_id` (optional): Instance ID for multi-instance setups

**Return**:

```yaml
success: true
state: "heating_processing"
time_recovery_start: "2026-02-04T04:30:15+01:00"
rcth_calculated: 52.3
message: "Recovery started"
```

**Example call**:

```yaml
service: smarthrtx.start_recovery
```

**⚠️ Note**: This service is normally called automatically at `recovery_start_hour`.

---

### `end_recovery`

**Usage**: Ends the recovery phase

**Transition**: `HEATING_PROCESSING` → `HEATING_ON`

**Description**:

- Calculates RPth (thermal power constant)
- Returns to normal heating mode
- Updates learned coefficients

**Parameters**:

- `entry_id` (optional): Instance ID for multi-instance setups

**Return**:

```yaml
success: true
state: "heating_on"
time_recovery_end: "2026-02-04T06:00:00+01:00"
rpth_calculated: 48.7
message: "Recovery ended"
```

**Example call**:

```yaml
service: smarthrtx.end_recovery
```

**⚠️ Note**: This service is normally called automatically at `target_hour` (wake-up time) or when the setpoint is reached.

---

### `get_state`

**Usage**: Returns the complete system state

**Parameters**:

- `entry_id` (optional): Instance ID for multi-instance setups

**Return**:

```yaml
success: true
state: "monitoring"
smartheating_mode: true
recovery_calc_mode: true
rp_calc_mode: false
temp_lag_detection_active: false
interior_temp: 18.5
exterior_temp: 2.3
target_hour: "06:00:00"
recoverycalc_hour: "23:00:00"
recovery_start_hour: "2026-02-04T04:30:00+01:00"
time_to_recovery_hours: 5.2
rcth: 52.3
rpth: 48.7
```

**Example call**:

```yaml
service: smarthrtx.get_state
response_variable: state_info
```

---

## Utility Services

### `reset_learning`

Resets all learned thermal coefficients to default values (50).

**Usage**: After home modifications or if learned values are inaccurate

**Parameters**:

- `entry_id` (optional): Instance ID for multi-instance setups

**Example**:

```yaml
service: smarthrtx.reset_learning
```

---

### `trigger_calculation`

Immediately triggers a new recovery time calculation.

**Usage**: After parameter changes to see the effect immediately

**Parameters**:

- `entry_id` (optional): Instance ID for multi-instance setups

**Example**:

```yaml
service: smarthrtx.trigger_calculation
```

---

## Legacy Services (Deprecated)

These services are kept for compatibility but their use is **discouraged**.
Use the simplified services instead:

| Legacy service                   | Replaced by           |
| -------------------------------- | --------------------- |
| `calculate_recovery_time`        | `trigger_calculation` |
| `on_heating_stop`                | `stop_heating`        |
| `on_recovery_start`              | `start_recovery`      |
| `on_recovery_end`                | `end_recovery`        |
| `calculate_rcth_fast`            | Internal use only     |
| `calculate_recovery_update_time` | Internal use only     |

---

## Automation Examples

### Complete manual cycle

```yaml
# Automation 1: Stop heating in the evening
automation:
  - alias: "SmartHRTX - Stop heating at 11 PM"
    trigger:
      - platform: time
        at: "23:00:00"
    action:
      - service: smarthrtx.stop_heating

# Automation 2: Start recovery (automatic via recovery_start_hour)
# No automation needed, SmartHRTX triggers automatically

# Automation 3: End recovery at wake-up
automation:
  - alias: "SmartHRTX - End recovery at wake-up"
    trigger:
      - platform: time
        at: "06:00:00"
    action:
      - service: smarthrtx.end_recovery
```

### Force a new cycle

```yaml
automation:
  - alias: "SmartHRTX - Reset cycle after absence"
    trigger:
      - platform: state
        entity_id: person.home
        to: "home"
    action:
      - service: smarthrtx.start_heating_cycle
```

### Debug and monitoring

```yaml
automation:
  - alias: "SmartHRTX - Log state every hour"
    trigger:
      - platform: time_pattern
        hours: "/1"
    action:
      - service: smarthrtx.get_state
        response_variable: state
      - service: system_log.write
        data:
          message: "SmartHRTX state: {{ state.state }}, Recovery in: {{ state.time_to_recovery_hours }}h"
          level: info
```

---

## Multi-Instance

If you have multiple SmartHRTX instances configured, you must specify the `entry_id` parameter to target a specific instance:

```yaml
service: smarthrtx.stop_heating
data:
  entry_id: "abc123def456"
```

To find your `entry_id`, check the logs at startup or use Home Assistant's Developer Tools.

---

## Important Notes

1. **Automatic mode**: In most cases, you don't need to call these services manually. SmartHRTX automatically manages state transitions.

2. **Recommended services**: Always prefer simplified services (`start_heating_cycle`, `stop_heating`, etc.) over legacy services.

3. **Service responses**: All services return a dictionary with at minimum `success` (bool) and contextual information. Use `response_variable` to capture this data in your automations.

4. **Transient states**: Some states are transient (DETECTING_LAG, RECOVERY) and may be very short in duration.
