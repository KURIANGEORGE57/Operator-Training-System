"""Configuration constants for the BTX Benzene Column OTS."""

# Safety thresholds (guardrails)
SAFETY_LIMITS = {
    "dP_alarm": 0.30,
    "dP_trip": 0.33,
    "dP_esd": 0.34,
    "T_top_alarm": 100.0,
    "T_top_esd": 103.0,
    "xB_spec": 0.9990,
    "L_drum_min": 0.10,
    "L_drum_crit": 0.05,
}

# UI slider configurations
SLIDER_CONFIG = {
    "fouling_condenser": {"min": 0, "max": 60, "default": 0, "step": 5},
    "fouling_reboiler": {"min": 0, "max": 60, "default": 0, "step": 5},
    "feed_benzene": {"min": 0.45, "max": 0.75, "default": 0.60, "step": 0.01},
    "feed_rate": {"min": 50, "max": 120, "default": 80, "step": 1},
    "SP_F_Reflux": {"min": 10.0, "max": 45.0, "step": 0.5},
    "SP_F_Reboil": {"min": 0.3, "max": 3.5, "step": 0.1},
    "SP_F_ToTol": {"min": 30.0, "max": 90.0, "step": 0.5},
}

# Per-turn move rate caps
MOVE_RATE_CAPS = {
    "SP_F_Reflux": 2.0,
    "SP_F_Reboil": 0.15,
    "SP_F_ToTol": 5.0,
}

# Safety interlock adjustments
INTERLOCK_ADJUSTMENTS = {
    "reboil_decrease": 0.2,
    "reflux_increase": 2.0,
    "reboil_min": 0.3,
    "reflux_max": 45.0,
}

# Default values
DEFAULTS = {
    "L_drum_fallback": 0.5,
}

# Event log display
EVENT_LOG_LINES = 15

# Controller limits for controller.decide()
CONTROLLER_LIMITS = {
    "reflux": (10.0, 45.0),
    "reboil": (0.3, 3.5),
    "totol": (30.0, 90.0),
}
