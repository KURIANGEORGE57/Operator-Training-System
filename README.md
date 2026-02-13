# Benzene Column Operator Training System

A turn-based distillation process simulator for training operators on safe
benzene-toluene column operation. Features physics-based plant dynamics, a
three-tier safety system, multiple control strategies, and performance scoring.

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

The application opens at `http://localhost:8501`.

## Features

- **Physics-based plant model** with first-order dynamics and VLE correlations
- **Three-tier safety system**: alarms, interlocks, emergency shutdown (ESD)
- **Multiple control modes**: manual operation, NN policy, linear MPC
- **Scenario library**: 7 pre-built scenarios from beginner to advanced, plus custom
- **Performance scoring**: per-turn scoring with purity, pressure, level, and safety components
- **Process schematic**: live Pillow-rendered flow diagram with safety badges
- **Trend charts**: historical plots for purity, dP, temperature, and levels
- **Event log**: full audit trail of alarms, interlocks, and operator actions

## Key Process Variables

| Variable | Description | Normal Range | Units |
|----------|-------------|--------------|-------|
| xB_sd | Benzene purity (side-draw) | 0.999+ | mol fraction |
| dP_col | Column differential pressure | 0.08-0.25 | bar |
| T_top | Overhead temperature | 80-95 | deg C |
| F_Reflux | Reflux flow rate | 20-35 | t/h |
| F_Reboil | Reboiler duty | 1.0-1.5 | MW |
| F_ToTol | Toluene transfer rate | 45-65 | t/h |

## Safety Thresholds

| Condition | Alarm | Interlock | ESD |
|-----------|-------|-----------|-----|
| Column dP | >0.30 bar | >0.33 bar | >0.34 bar |
| Overhead T | >100 C | - | >103 C |
| Drum Level | <0.10 | - | <0.05 |
| Benzene Purity | <0.9990 | - | - |

## Project Structure

```
Operator-Training-System/
├── app.py                          # Main Streamlit application
├── requirements.txt                # Dependencies
├── src/
│   ├── models/
│   │   ├── constants.py            # Safety limits, ranges, steady state
│   │   ├── plant_state.py          # Immutable plant state dataclass
│   │   └── plant.py                # Physics engine + move rate limiting
│   ├── safety/
│   │   └── safety_system.py        # Three-tier safety evaluation
│   ├── controllers/
│   │   ├── base.py                 # Controller interface
│   │   ├── nn_controller.py        # NN heuristic controller
│   │   └── mpc_controller.py       # Linear MPC (2x2, CVXPY/OSQP)
│   ├── scenarios/
│   │   └── library.py              # Pre-built training scenarios
│   ├── scoring/
│   │   └── tracker.py              # Performance scoring system
│   └── ui/
│       ├── sidebar.py              # Scenario + controller selection
│       ├── dashboard.py            # KPI metrics display
│       ├── controls.py             # Operator control sliders
│       ├── schematic.py            # Process flow diagram (Pillow)
│       ├── trends.py               # Historical trend charts
│       └── event_log.py            # Safety event log
├── tests/
│   ├── test_plant.py               # Plant model + rate limiting tests
│   ├── test_safety.py              # Safety system tests (3 tiers)
│   ├── test_controllers.py         # Controller output tests
│   ├── test_scoring.py             # Scoring system tests
│   └── test_scenarios.py           # Scenario library tests
└── .devcontainer/
    └── devcontainer.json           # VS Code dev container
```

## Testing

```bash
pytest tests/ -v
```

## Dependencies

| Package | Purpose |
|---------|---------|
| streamlit | Web UI framework |
| numpy | Numerical computations |
| pandas | Data handling for trends |
| Pillow | Process schematic rendering |
| cvxpy | MPC convex optimization |
| osqp | Quadratic programming solver |
| pytest | Testing framework |

## Architecture

The simulation uses a **two-phase commit** pattern:

1. `plant.step(u, scenario)` computes a tentative next state (no side effects)
2. `evaluate_safety(x_next, u)` checks all three safety tiers
3. Based on result: `plant.commit(x_next)`, apply interlock adjustments, or trigger ESD

Move rate limiting (`cap_moves`) constrains per-turn changes to physically
realistic actuator rates before the step is evaluated.

---

**Safety Notice**: This is a training simulator. Real chemical plant operations
require proper safety protocols, certified equipment, and trained personnel.
