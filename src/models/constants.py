"""Physical constants, safety limits, and operational ranges for the benzene column."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyLimits:
    """Three-tier safety thresholds."""

    # Column differential pressure (bar)
    dP_alarm: float = 0.30
    dP_interlock: float = 0.33
    dP_esd: float = 0.34

    # Overhead temperature (deg C)
    T_top_alarm: float = 100.0
    T_top_esd: float = 103.0

    # Benzene purity specification (mol fraction)
    xB_spec: float = 0.9990

    # Reflux drum level (fraction 0-1)
    L_drum_alarm: float = 0.10
    L_drum_esd: float = 0.05

    # Bottoms level (fraction 0-1)
    L_bot_alarm: float = 0.10


LIMITS = SafetyLimits()


# Nominal steady-state operating point
STEADY_STATE = {
    "xB_sd": 0.9950,     # Benzene side-draw purity (mol fraction)
    "dP_col": 0.08,      # Column differential pressure (bar)
    "T_top": 84.5,       # Overhead temperature (deg C)
    "L_Drum": 0.65,      # Reflux drum level (0-1)
    "L_Bot": 0.56,       # Bottoms level (0-1)
    "F_Reflux": 25.0,    # Reflux flow (t/h)
    "F_Reboil": 1.20,    # Reboiler duty (MW)
    "F_ToTol": 55.0,     # Toluene transfer (t/h)
}


# Per-turn move rate limits for actuators
MOVE_CAPS = {
    "SP_F_Reflux": 2.0,   # t/h per turn
    "SP_F_Reboil": 0.15,  # MW per turn
    "SP_F_ToTol": 5.0,    # t/h per turn
}


# Actuator operating ranges
ACTUATOR_RANGES = {
    "SP_F_Reflux": (10.0, 45.0),
    "SP_F_Reboil": (0.3, 3.5),
    "SP_F_ToTol": (30.0, 90.0),
}


# Default scenario
DEFAULT_SCENARIO = {
    "F_feed": 80.0,        # Feed flow rate (t/h)
    "zB_feed": 0.60,       # Benzene fraction in feed
    "Fouling_Cond": 0.0,   # Condenser fouling (0-1)
    "Fouling_Reb": 0.0,    # Reboiler fouling (0-1)
}
