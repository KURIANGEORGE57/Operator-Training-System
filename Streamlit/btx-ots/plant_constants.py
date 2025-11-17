"""Physical and numerical constants for the PlantNeqSim model."""

# Column specification defaults
COLUMN_SPEC_DEFAULTS = {
    "overhead_pressure_bar": 1.6,
    "condenser_duty_tau": 0.5,
    "reboiler_tau": 0.5,
    "inventory_tau": 0.25,
    "feed_temperature_c": 95.0,
    "feed_pressure_bar": 2.2,
}

# Initial state values
INITIAL_STATE = {
    "xB_sd": 0.9950,   # benzene purity (side-draw)
    "dP_col": 0.08,    # bar
    "T_top": 84.5,     # °C
    "L_Drum": 0.65,    # 0..1
    "L_Bot":  0.56,    # 0..1
    "F_Reflux": 25.0,  # t/h (actual)
    "F_Reboil": 1.20,  # MW eq. (proxy)
    "F_ToTol":  55.0,  # t/h
}

# Variable bounds for clipping
VARIABLE_BOUNDS = {
    "xB_sd": (0.90, 0.9999),
    "dP_col": (0.02, 0.40),
    "T_top": (60.0, 110.0),
    "L_Drum": (0.0, 1.0),
    "L_Bot": (0.0, 1.0),
    "F_Reflux": (10.0, 45.0),
    "F_Reboil": (0.3, 3.5),
    "F_ToTol": (30.0, 90.0),
}

# Minimum composition values to avoid singularities
MIN_COMPOSITION = 1e-5
MIN_FLOW_RATE = 1e-3

# Temperature conversions and reference values
KELVIN_OFFSET = 273.15
INITIAL_TEMP_GUESS_K = 350.0

# VLE correlation fallback constants
VLE_FALLBACK = {
    "benzene_bp_c": 80.1,      # benzene boiling point at ~1 atm
    "toluene_shift_c": 21.0,   # toluene heavier -> hotter
    "toluene_exponent": 0.85,
}

# Signature rounding precision
SIGNATURE_PRECISION = {
    "flow_tph": 1,    # decimal places
    "zB": 4,          # decimal places
}

# Level dynamics coefficients
LEVEL_DYNAMICS = {
    "drum_reflux_coeff": 0.0025,
    "drum_totol_coeff": -0.0015,
    "drum_feed_coeff": 0.0010,
    "bot_feed_coeff": 0.0012,
    "bot_totol_coeff": -0.0016,
    "bot_reboil_coeff": -0.0010,
}

# Purity dynamics coefficients
PURITY_DYNAMICS = {
    "reflux_gain": 0.0040,
    "reflux_nominal": 25.0,
    "reflux_scale": 10.0,
    "reboil_gain": 0.0030,
    "reboil_nominal": 1.2,
    "feed_gain": 0.0025,
    "feed_nominal": 0.60,
    "feed_scale": 0.05,
    "cond_fouling_penalty": -0.0040,
    "reb_fouling_penalty": -0.0030,
}

# Pressure drop dynamics coefficients
PRESSURE_DROP_DYNAMICS = {
    "cond_fouling_coeff": 0.012,
    "feed_dev_coeff": 0.010,
    "feed_nominal": 80.0,
    "feed_scale": 40.0,
    "reflux_coeff": 0.006,
    "reflux_nominal": 25.0,
    "reflux_scale": 15.0,
    "totol_coeff": -0.004,
    "totol_nominal": 55.0,
    "totol_scale": 15.0,
}

# Overhead temperature estimation
OVERHEAD_TEMP = {
    "benzene_base_purity": 0.92,
    "benzene_purity_gain": 0.06,
    "purity_nominal": 0.992,
    "purity_scale": 0.008,
    "fouling_penalty": -0.05,
    "cond_fouling_temp_bias": 12.0,
    "reb_fouling_temp_bias": 6.0,
    "min_benzene_reflux": 0.85,
    "max_benzene_reflux": 0.998,
    "benzene_clip_min": 1e-4,
    "benzene_clip_max": 0.9999,
}

# ESD safe state setpoints
ESD_SAFE_STATE = {
    "F_Reflux": 20.0,
    "F_Reboil": 0.5,
    "F_ToTol": 45.0,
    "xB_sd_decrease": 0.002,
    "xB_sd_min": 0.90,
    "dP_col_max": 0.25,
    "T_top_decrease": 5.0,
}

# Default scenario values
DEFAULT_SCENARIO = {
    "F_feed": 80.0,
    "zB_feed": 0.60,
    "Fouling_Cond": 0.0,
    "Fouling_Reb": 0.0,
}
