# SmartHRTX Architecture Guide

**Technical architecture, design patterns, and thermal calculations**

## System Overview

SmartHRTX is a Home Assistant custom integration built on the **DataUpdateCoordinator** pattern. It automates heating startup calculations using adaptive thermal modeling.

```
┌───────────────────────────────────────────────────┐
│         Home Assistant Core                       │
├───────────────────────────────────────────────────┤
│  ConfigEntry ──► SmartHRTCoordinator ◄── Services │
│                       │                           │
│     ┌─────────────────┼──────────────┐            │
│     ▼                 ▼              ▼            │
│  Weather Entity   Config Data    Temperature Data │
│                       │                           │
│  ┌────────────────────┴──────────────────┐        │
│  │  Entities (Sensors/Switches/Numbers)  │        │
│  │  - Predictions                        │        │
│  │  - Thermal coefficients               │        │
│  │  - Mode controls                      │        │
│  └───────────────────────────────────────┘        │
└───────────────────────────────────────────────────┘
```

## State Machine

SmartHRTX uses a **6-state finite state machine** to manage the daily heating cycle. The system
starts in `INITIALIZING` on every boot and restores the previously persisted state; the remaining
five states form the repeating daily loop.

```
    ┌─────────────────────────────────────────────────────────────────┐
    │                       Repeating daily loop                      │
    │                                                                 │
    │  ~Evening                ~Night              ~Morning  ~Wake-up │
    │     │                      │                    │          │    │
    │     ▼                      ▼                    ▼          ▼    │
    │  HEATING_ON ──► DETECTING_LAG ──► MONITORING ──► RECOVERY ──► HEATING_PROCESS ──┐
    │     ▲                                │                               │           │
    │     └───────────────────────────────────────────────────────────────┘           │
    │                                      │ (already at target temp)                 │
    │                                      └──────────────────► HEATING_PROCESS ──────┘
    └─────────────────────────────────────────────────────────────────┘

INITIALIZING ──► any state  (on every HA restart, restores persisted state)
```

### Understanding the Naming

The state names can be confusing at first because **"HEATING_ON" does not mean the physical
heater is running right now**. Think of it as "in the normal daily operating mode." The heater
runs or stops under your normal Home Assistant automations — SmartHRTX only kicks in at specific
transition points to observe temperatures and learn.

The word **"Recovery"** refers to the morning re-heat: after overnight cooling, the room needs to
"recover" its heat before wake-up. The lag-detection phase happens in the *evening*, not during
this morning recovery.

### State Descriptions

| State               | When you enter it                                              | What happens inside                                            | Exits to            |
| ------------------- | -------------------------------------------------------------- | -------------------------------------------------------------- | ------------------- |
| **INITIALIZING**    | Every HA (re)start                                             | Restores persisted state; schedules any needed timers          | Any state (restore) |
| **HEATING_ON**      | Daily idle — after the morning cycle completes                 | SmartHRTX is passive; normal automations control the heater   | DETECTING_LAG       |
| **DETECTING_LAG**   | `stop_heating` service called (evening heater shuts off)       | Watches for a 0.2°C indoor drop to confirm cooling has begun; records the lag timestamp | MONITORING |
| **MONITORING**      | Cooling confirmed (lag detected)                               | Calculates when heating must restart; sets a wake-up timer     | RECOVERY (or HEATING_PROCESS if already at target) |
| **RECOVERY**        | Timer fires at the calculated restart time (morning)           | Heating turns on; measures actual warm-up rate to calibrate RPth | HEATING_PROCESS  |
| **HEATING_PROCESS** | Target wake-up hour reached                                    | Snapshots final temperature; updates RPth with exponential relaxation; saves coefficients; resets to idle | HEATING_ON |

### A Concrete Day in the Life

```
18:00  Your evening automation turns the heater off.
       You call smarthrtx.stop_heating → state: HEATING_ON → DETECTING_LAG

18:07  Indoor temp has dropped 0.2°C since the heater stopped.
       Lag confirmed → state: DETECTING_LAG → MONITORING
       Recovery start time calculated and timer scheduled.

02:30  Calculated restart time fires.
       state: MONITORING → RECOVERY
       RCth updated from overnight cooling curve.
       Heating turns on.

06:00  Target wake-up hour reached.
       state: RECOVERY → HEATING_PROCESS
       RPth updated from measured warm-up rate.
       Data saved.  state: HEATING_PROCESS → HEATING_ON
```

## Thermal Model

SmartHRTX models your home using **two key constants:**

### RCth - Cooling Constant

Measures how fast your room loses heat when heating is off.

**Newton's Law of Cooling:**
$$T(t) = T_{outside} + (T_{initial} - T_{outside}) \cdot e^{-t/RC_{th}}$$

**Interpretation:**

- High RCth = good insulation (heat loss is slow)
- Low RCth = poor insulation (heat loss is fast)

### RPth - Heating Constant

Measures how fast heating warms your room.

**Heating formula:**
$$T(t) = T_{target} - (T_{target} - T_{initial}) \cdot e^{-t/RP_{th}}$$

**Interpretation:**

- High RPth = fast heating (powerful system)
- Low RPth = slow heating (weak system)

## Wind Adaptation

Both RCth and RPth vary with wind speed using **linear interpolation:**

$$C(wind) = C_0 + (C_w - C_0) \cdot \frac{wind}{wind_{max}}$$

Where:

- $C_0$ = coefficient at zero wind
- $C_w$ = coefficient at maximum wind
- The system automatically learns both values

**Effect:**

- More wind → faster cooling → lower RCth → earlier heating start
- Calm conditions → slower cooling → higher RCth → later heating start

## Learning Process

### Phase 1: Detect Lag (Evening to Night)

After heating stops, monitor temperature drop to identify the thermal time constant.

### Phase 2: Calculate Recovery Time (Night)

Use RCth and RPth to predict when to start heating.

### Phase 3: Measure Heating Rate (Morning)

During heating, measure actual heating speed to update RPth.

### Calibration Strategy

Uses **exponential relaxation** for smooth learning:

$$C_{new} = C_{old} + \alpha \cdot (C_{measured} - C_{old})$$

Where $\alpha$ (learning rate) decays over time for stability.

## Data Model

### Core Configuration

```
- zone_name: Name of the heating zone
- target_hour: When to reach target temperature
- heating_stop_hour: When to turn off heating
- interior_temp_sensor: Room thermometer
- weather_entity: Weather source
- target_temperature: Desired temperature (°C)
```

### Learned Coefficients (Persistent)

```
- rc_thermal: Cooling constant (1-200 hours)
- rc_thermal_windy: Cooling at max wind (1-200 hours)
- rp_thermal: Heating constant (0.1-50 hours)
- rp_thermal_windy: Heating at max wind (0.1-50 hours)
- temperature_lag: Heating detection delay (minutes)
```

### Calculated Values (Real-time)

```
- recovery_start_time: When to start heating (HH:MM)
- recovery_duration: How long heating will run (minutes)
- interior_temperature: Current room temperature
- exterior_temperature: Outside temperature
```

## Entity Platform Distribution

### Sensors (Read-only data)

- Interior/exterior temperatures
- Recovery predictions
- Status information

### Numbers (Adjustable coefficients)

- RCth and RPth for manual tuning
- Temperature lag threshold
- Learning rate

### Switches (Mode controls)

- Enable/disable learning
- Manual mode overrides

### Times (User preferences)

- Target hour (wake-up time)
- Heating stop hour

## Services

### smarthrtx.on_heating_stop

Called when heating stops (evening). Records baseline temperature for next calculation.

### smarthrtx.on_recovery_start

Called when heating starts (morning). Triggers RPth measurement mode.

### smarthrtx.on_recovery_end

Called at target hour. Finalizes learning and resets for next day.

## Persistence

**Storage:** Home Assistant's built-in data store (not YAML)

**Persisted Data:**

- RCth and RPth coefficients
- Wind adjustment factors
- Temperature lag measurements
- Learning rate and decay

**Update Frequency:**

- Every morning after recovery phase
- Smooth exponential updates (not instant)

## Wind Speed Integration

Wind data comes from the weather entity (3-hour forecast window). SmartHRTX automatically:

1. Reads current/forecasted wind speed
2. Interpolates thermal coefficients
3. Recalculates recovery time if wind changes significantly

## Validation & Safety

The system includes bounds checking:

- RCth: 1-200 hours (invalid values reset to defaults)
- RPth: 0.1-50 hours
- Temperature lag: 0-120 minutes
- Recovery time: Never less than 5 minutes, max 12 hours

Out-of-bounds values trigger warnings but don't crash the system.

---
