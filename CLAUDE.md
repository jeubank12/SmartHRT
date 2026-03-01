# SmartHRTX — Claude Context

## Project Summary

**SmartHRTX** is a Home Assistant custom integration that calculates the optimal heating start time each morning so the room reaches the target temperature at wake-up. It uses Newton's Law of Cooling and learns two thermal constants (RCth, RPth) that improve over time.

This is a **fork** of [CorentinBarban/SmartHRT](https://github.com/CorentinBarban/SmartHRT). The fork lives at [jeubank12/SmartHRT](https://github.com/jeubank12/SmartHRT) — the **GitHub repo is named `SmartHRT`** but the project and integration are called **SmartHRTX**.

## Key Names to Keep Straight

| Thing | Value |
|---|---|
| GitHub repo URL | `https://github.com/jeubank12/SmartHRT` |
| HA integration domain | `smarthrtx` |
| HACS install path | `/config/custom_components/smarthrtx/` |
| HA services prefix | `smarthrtx.*` |
| Upstream (original) | `CorentinBarban/SmartHRT` (domain: `smarthrt`) |

> **Why the mismatch?** The GitHub repo was not renamed when the integration was rebranded to SmartHRTX. The repo name doesn't affect the HACS install path — HACS reads the `domain` field from `manifest.json`.

## Repository Structure

```
SmartHRT/
├── custom_components/smarthrtx/   # Integration source (domain = smarthrtx)
│   ├── manifest.json              # domain, version, codeowners
│   ├── __init__.py                # Setup/teardown, services wiring
│   ├── coordinator.py             # Core logic & state machine
│   ├── config_flow.py             # UI config + options flow
│   ├── const.py                   # DOMAIN = "smarthrtx", all constants
│   ├── services.py                # Service handlers
│   ├── sensor/switch/number/time  # Entity platforms
│   └── strings.json               # UI labels
├── tests/                         # pytest tests
├── docs/
│   ├── GUIDE.md                   # User installation & config guide
│   ├── ARCHITECTURE.md            # Thermal model, state machine details
│   ├── SERVICES.md                # All HA services (smarthrtx.*)
│   └── CONTRIBUTING.md            # Dev setup & workflow
├── ADR/                           # Architecture Decision Records
├── hacs.json                      # HACS metadata (name: SmartHRTX)
├── pyproject.toml                 # Python project config
└── CLAUDE.md                      # This file
```

## Development Setup

```bash
# Start HA dev server (port 8123)
uv run .devcontainer/hass.sh

# Start with debugger (port 5678)
uv run .devcontainer/hass_debug.sh

# Run tests
pytest

# Lint
pylint custom_components/smarthrtx/*.py
black .
```

Dev container is configured in `.devcontainer/` — preferred for VS Code.

## State Machine (6 states)

```
INITIALIZING → (restored state)   ← every HA restart lands here first

HEATING_ON → DETECTING_LAG → MONITORING → RECOVERY → HEATING_PROCESS → HEATING_ON
```

- **INITIALIZING**: Transient boot state; restores persisted state and exits immediately
- **HEATING_ON**: Daily idle — SmartHRTX is passive; normal automations control the heater
- **DETECTING_LAG**: Evening, heater just stopped; waits for 0.2°C drop to confirm cooling and record lag
- **MONITORING**: Cooling confirmed; waits for calculated morning restart time
- **RECOVERY**: Morning re-heat underway; measures actual warm-up rate (RPth calibration)
- **HEATING_PROCESS**: Wake-up hour reached; finalises RPth, saves coefficients, resets to idle

> **Naming note:** `HEATING_ON` does **not** mean the physical heater is running — it is the
> resting/idle state between cycles. "Recovery" means recovering room heat lost overnight.

## Thermal Constants

- **RCth**: How fast the room cools (cooling time constant, hours)
- **RPth**: How fast the room heats (heating time constant, hours)
- Both vary with wind speed (linear interpolation between calm/windy values)
- Stored persistently via HA's data store; updated daily with exponential relaxation

## Key Design Decisions

See `ADR/` directory for Architecture Decision Records.

- Unit handling (°C/°F): user selects preference in config flow; all internal calculations use °C
- Timestamp sensors (`device_class: timestamp`) allow using heating times as automation triggers
- Services are domain-scoped: `smarthrtx.stop_heating`, `smarthrtx.start_recovery`, etc.

## Upstream Relationship

This fork adds quality-of-life tweaks on top of CorentinBarban's integration. A PR contributing changes back upstream is planned. When referencing the upstream, always use `CorentinBarban/SmartHRT` — **never** point users to the upstream repo for installation (they'd get `domain: smarthrt` and the wrong install path).
