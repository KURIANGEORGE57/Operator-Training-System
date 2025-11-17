# Operator Training System (OTS)

A safety-critical operator training simulator for chemical process control, featuring multiple training environments for benzene-toluene distillation and heat exchanger operations.

## Overview

This repository contains operator training simulators designed to teach process control concepts and safe operation of chemical plants. The system features:

- **Three training applications** with different process units and complexity levels
- **Physics-based plant models** with optional NeqSim thermodynamic calculations
- **Three-tier safety system** (alarms, interlocks, emergency shutdown)
- **What-if scenario analysis** (fouling, failures, upsets)
- **Multiple control strategies** (manual operation, neural network policy, MPC)
- **Interactive Streamlit interfaces** for realistic operator experience

## 🎯 Applications

### 1. BTX Operator Training System (Primary)

**Location:** `Streamlit/btx-ots/`

A production-ready, turn-based benzene column training simulator with advanced safety systems.

#### Features

- **Realistic Physics**: NeqSim-backed thermodynamics with graceful fallback to correlations
- **Safety-Critical Systems**:
  - Alarms (high ΔP, high temperature, off-spec purity, low levels)
  - Interlocks (automatic protective actions for flooding)
  - Emergency Shutdown (ESD) for critical conditions
- **Control Options**:
  - Manual operator control with rate-limited moves
  - Neural network policy controller
  - Linear Model Predictive Control (MPC)
- **Scenario Management**: Configurable feed rates, compositions, and fouling
- **Process Visualization**: Real-time schematic with status badges
- **Event Logging**: Complete audit trail of alarms and operator actions

#### Quick Start

```bash
cd Streamlit/btx-ots
pip install -r requirements.txt
streamlit run app.py
```

The application will open at `http://localhost:8501`

#### Key Process Variables

| Variable | Description | Normal Range | Units |
|----------|-------------|--------------|-------|
| xB_sd | Benzene purity (side-draw) | 0.999+ | mol fraction |
| dP_col | Column differential pressure | 0.08-0.25 | bar |
| T_top | Overhead temperature | 80-95 | °C |
| F_Reflux | Reflux flow rate | 20-35 | t/h |
| F_Reboil | Reboiler duty | 1.0-1.5 | MW |
| F_ToTol | Toluene transfer rate | 45-65 | t/h |

#### Safety Thresholds

| Condition | Alarm | Interlock | ESD |
|-----------|-------|-----------|-----|
| Column ΔP | >0.30 bar | >0.33 bar | >0.34 bar |
| Overhead T | >100°C | - | >103°C |
| Drum Level | <0.10 | - | <0.05 |
| Benzene Purity | <0.9990 | - | - |

### 2. Heat Exchanger Operator Training System

**Location:** `Streamlit/hx-ots/`

A turn-based shell-and-tube heat exchanger simulator with realistic what-if scenarios and failure modes.

#### Features

- **Realistic Physics**: Counter-flow heat exchanger with effectiveness-NTU model
- **Safety-Critical Systems**:
  - Alarms (high temperatures, high ΔP, fouling, tube leaks)
  - Interlocks (automatic flow adjustments for protection)
  - Emergency Shutdown (ESD) for critical conditions
- **What-If Scenarios**:
  - Fouling (hot and cold side, gradual degradation)
  - Tube leakage (hot fluid contamination of cold side)
  - Pump trips (flow loss scenarios)
  - Temperature upsets (feed temperature changes)
- **Process Visualization**: ASCII schematic with real-time status
- **Event Logging**: Complete audit trail of alarms and actions

#### Quick Start

```bash
cd Streamlit/hx-ots
pip install -r requirements.txt
streamlit run app.py
```

The application will open at `http://localhost:8501`

#### Key Process Variables

| Variable | Description | Normal Range | Units |
|----------|-------------|--------------|-------|
| T_hot_out | Hot outlet temperature | 55-70 | °C |
| T_cold_out | Cold outlet temperature | 40-50 | °C |
| F_hot | Hot side flow rate | 25-40 | kg/s |
| F_cold | Cold side flow rate | 40-60 | kg/s |
| Q_duty | Heat duty | 6000-9000 | kW |
| dP_hot | Hot side pressure drop | 0.5-1.5 | bar |
| dP_cold | Cold side pressure drop | 0.2-0.8 | bar |

#### Safety Thresholds

| Condition | Alarm | Interlock | ESD |
|-----------|-------|-----------|-----|
| Hot Outlet T | >140°C | >145°C | >150°C |
| Cold Outlet T | >55°C | - | >60°C |
| Hot Side ΔP | >2.0 bar | >2.3 bar | >2.5 bar |
| Cold Side ΔP | >1.2 bar | - | >1.5 bar |
| Fouling | >50% | >75% | - |
| Tube Leak | >10% | - | >30% |

#### What-If Scenarios

**1. Fouling Accumulation**
- Gradually reduces heat transfer effectiveness
- Increases pressure drop
- Requires increased cooling flow or shutdown for cleaning

**2. Tube Leakage**
- Hot process fluid leaks into cooling water
- Contaminates cold side, raises cold inlet temperature
- Critical leaks trigger ESD

**3. Pump Trips**
- Hot or cold pump failure
- Loss of flow causes poor heat transfer
- May trigger temperature alarms

**4. Temperature Upsets**
- High hot inlet temperature from upstream process
- Can cause outlet temperature alarms
- Requires increased cooling to compensate

### 3. MVP Training Environment (Simplified)

**Location:** `app.py` (root level)

A simpler training environment for basic process control concepts.

#### Features

- **Simplified Plant Model**: Basic level, temperature, and pressure dynamics
- **Fault Injection**: Heater fouling, pump trips, sensor drift
- **Performance Scoring**: Real-time metrics for operator performance
- **Steady-State Mapping**: First-order dynamics around setpoints

#### Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 🏗️ Architecture

### Plant Models

All plant models inherit from `PlantBase` abstract class:

```
PlantBase (abstract)
├── PlantNeqSim (production BTX model)
├── PlantHeatExchanger (heat exchanger model)
└── Plant (legacy stub model)
```

**Common Interface:**
- `state`: Current plant state dictionary
- `step(u, scenario)`: Compute next state (two-phase commit)
- `commit(x_next)`: Accept computed state
- `esd_safe_state()`: Emergency shutdown procedure

### Controllers

**Neural Network Policy** (`controllers/nn_controller.py`)
- Heuristic-based control policy
- Targets purity specification and pressure limits

**Linear MPC** (`controllers/mpc_controller.py`)
- 2×2 Model Predictive Control using CVXPY/OSQP
- Optimizes reflux and reboiler duty
- Constraints on rates and process limits

### Safety Systems

**Tier 1: Alarms** - Early warnings requiring operator attention

**Tier 2: Interlocks** - Automatic protective actions
- Example: Flooding interlock reduces reboiler, increases reflux

**Tier 3: Emergency Shutdown** - Last-resort safety measure
- Triggers safe plant configuration
- Cannot be overridden

**Move Rate Limiting** - Prevents dangerous control changes
- Reflux: ±2.0 t/h per turn
- Reboiler: ±0.15 MW per turn
- Toluene transfer: ±5.0 t/h per turn

## 🧪 Testing

Comprehensive unit tests for safety-critical logic:

**BTX Column Tests:**
```bash
cd Streamlit/btx-ots
pytest test_safety.py -v
```

Test Coverage (29 tests):
- ✅ All alarm conditions
- ✅ Interlock activation and limits
- ✅ ESD triggers and boundary conditions
- ✅ Move rate limiting
- ✅ Multi-tier safety integration

**Heat Exchanger Tests:**
```bash
cd Streamlit/hx-ots
pytest test_safety_hx.py -v
```

Test Coverage (19 tests):
- ✅ Temperature and pressure alarms
- ✅ Flow, fouling, and leak alarms
- ✅ Interlock protective actions
- ✅ ESD triggers (temperature, pressure, leak)
- ✅ Flow rate limiting

## 📦 Dependencies

### Core Requirements

| Package | Version | Purpose |
|---------|---------|---------|
| streamlit | 1.51.0 | Web interface framework |
| numpy | 2.3.5 | Numerical computations |
| pandas | 2.3.3 | Data handling |

### BTX Application

| Package | Version | Purpose |
|---------|---------|---------|
| Pillow | 12.0.0 | Process schematic rendering |
| cvxpy | 1.7.3 | MPC optimization |
| osqp | 1.0.5 | Quadratic programming solver |

### Optional

| Package | Purpose |
|---------|---------|
| neqsim | High-fidelity VLE thermodynamics (graceful fallback if unavailable) |

### Testing

| Package | Version | Purpose |
|---------|---------|---------|
| pytest | 9.0.1 | Unit testing framework |

## 🚀 Development

### Dev Container Support

The repository includes a `.devcontainer` configuration for VS Code:

```bash
# In VS Code with Remote-Containers extension:
# 1. Open folder in VS Code
# 2. Command Palette → "Reopen in Container"
# 3. Container auto-installs dependencies and launches BTX app
```

### Project Structure

```
Operator-Training-System/
├── app.py                      # MVP training environment
├── logger.py                   # Logging utilities
├── scoring.py                  # Performance scoring
├── requirements.txt            # Root dependencies
│
├── Streamlit/
│   │
│   ├── btx-ots/               # BTX Training System
│   │   ├── app.py             # Main Streamlit application
│   │   ├── plant_base.py      # Abstract plant model base class
│   │   ├── plant_neqsim.py    # NeqSim-backed plant model
│   │   ├── plant_stub.py      # Legacy correlation-based model
│   │   ├── test_safety.py     # Safety system unit tests
│   │   ├── requirements.txt   # BTX dependencies
│   │   │
│   │   ├── controllers/       # Control strategies
│   │   │   ├── nn_controller.py   # Neural network policy
│   │   │   └── mpc_controller.py  # Linear MPC
│   │   │
│   │   └── ui/                # UI components
│   │       └── image_panel.py # Process schematic renderer
│   │
│   └── hx-ots/                # Heat Exchanger Training System
│       ├── app.py             # Main Streamlit application
│       ├── plant_hx.py        # Heat exchanger plant model
│       ├── test_safety_hx.py  # Safety system unit tests
│       └── requirements.txt   # HX dependencies
│
├── sim_core/                  # Core simulation framework (scaffold)
│   └── plant_models.py
│
├── scenarios/                 # Scenario framework (scaffold)
│   └── base.py
│
└── .devcontainer/            # Dev container configuration
    └── devcontainer.json
```

## 🎓 Usage Examples

### Manual Operation (BTX App)

1. **Launch Application**
   ```bash
   cd Streamlit/btx-ots && streamlit run app.py
   ```

2. **Configure Scenario** (sidebar)
   - Set feed rate: 80 t/h
   - Set feed composition: 60% benzene
   - Add condenser fouling: 20%

3. **Operate the Column**
   - Adjust reflux, reboiler, and toluene transfer sliders
   - Click "Apply Operator Action"
   - Monitor alarms and interlocks
   - Click "Next Turn" to advance

4. **Safety Response**
   - Watch for alarm warnings (yellow)
   - Interlocks automatically adjust setpoints (orange)
   - ESD triggers safe shutdown if critical (red)

### Automated Control

1. Select "Linear MPC (2×2)" from sidebar
2. Click "Let Controller Decide"
3. Observe controller optimizing purity and pressure
4. Safety systems still active as backup

## 🛡️ Safety Features

### Two-Phase Commit Pattern

Plant models use a two-phase commit to enable safety checks:

```python
# Phase 1: Evaluate proposed action
x_next = plant.step(u=operator_setpoints, scenario=current_scenario)

# Phase 2: Check safety
safety_result = safety_logic(x_next, operator_setpoints)

if safety_result["esd"]:
    # Emergency shutdown - override all
    plant.esd_safe_state()
elif safety_result["adjust"]:
    # Interlock - adjust setpoints
    x_adjusted = plant.step(u=safety_result["adjust"], scenario=current_scenario)
    plant.commit(x_adjusted)
else:
    # Safe - proceed with operator action
    plant.commit(x_next)
```

### Error Handling

Robust error handling for NeqSim thermodynamic calculations:

- **Import Failures**: Logs info and falls back to correlations
- **Calculation Errors**: Logs warning and uses empirical relationships
- **Invalid Parameters**: Logs error details and provides safe fallback
- **Unexpected Errors**: Logs full exception and maintains stability

All errors are logged with context for debugging while maintaining safe operation.

## 🔧 Configuration

### Plant Model Selection

Edit `Streamlit/btx-ots/app.py` to switch plant models:

```python
# Use NeqSim-backed model (default)
from plant_neqsim import PlantNeqSim
st.session_state.plant = PlantNeqSim()

# Or use correlation-based stub
from plant_stub import Plant
st.session_state.plant = Plant()
```

### Safety Thresholds

Edit `LIMITS` dictionary in `Streamlit/btx-ots/app.py`:

```python
LIMITS = {
    "dP_alarm": 0.30,      # Alarm threshold for column ΔP
    "dP_trip": 0.33,       # Interlock activation
    "dP_esd": 0.34,        # Emergency shutdown
    "T_top_alarm": 100.0,  # Overhead temperature alarm
    "T_top_esd": 103.0,    # Overhead temperature ESD
    "xB_spec": 0.9990,     # Minimum benzene purity
    "L_drum_min": 0.10,    # Low drum level alarm
    "L_drum_crit": 0.05,   # Critical drum level ESD
}
```

## 📊 Performance Metrics

The MVP app includes performance scoring based on:

- **Setpoint Tracking**: Deviation from target levels
- **Stability**: Rate of change penalties
- **Safety**: Alarm and trip events
- **Efficiency**: Energy consumption

## 🤝 Contributing

This is a training system for educational purposes. When modifying safety-critical code:

1. **Run Tests**: `pytest Streamlit/btx-ots/test_safety.py -v`
2. **Verify Safety**: Test all three safety tiers
3. **Document Changes**: Update README and code comments
4. **Test Error Handling**: Verify graceful degradation

## 📝 License

[Specify your license here]

## 🙏 Acknowledgments

- **NeqSim**: Open-source thermodynamic library for process simulation
- **Streamlit**: Framework for building interactive data applications
- **CVXPY/OSQP**: Convex optimization tools for MPC implementation

## 📧 Support

For issues or questions:
- Open an issue in the GitHub repository
- Consult the code documentation
- Review unit tests for usage examples

---

**Safety Notice**: This is a training simulator. Real chemical plant operations require proper safety protocols, certified equipment, and trained personnel. Do not use this simulator for actual process control decisions.
