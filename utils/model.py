"""
The fiscal-injection model: point prediction, 90% interval, and shock
counterfactuals. All numbers pulled from config.py.
"""

import numpy as np

from config import MAIN_MODEL, SHOCKS, Z_CRIT, Z_DISTRESS_CUTOFF, Z_SAFE_CUTOFF


def predict(z):
    """Point prediction and (lower, upper) of the CI, given Z_{t-1}."""
    b0, b1 = MAIN_MODEL["b0"], MAIN_MODEL["b1"]
    se_b0, se_b1 = MAIN_MODEL["se_b0"], MAIN_MODEL["se_b1"]

    point = b0 + b1 * z
    # Approximation: treats the slope and intercept errors as independent
    # (ignores their covariance, which we don't have yet). Replace with a
    # proper joint interval once the full covariance matrix is available.
    se = np.sqrt(se_b1**2 * z**2 + se_b0**2)
    return point, point - Z_CRIT * se, point + Z_CRIT * se


def zone(z):
    if z < Z_DISTRESS_CUTOFF:
        return "Distress"
    if z < Z_SAFE_CUTOFF:
        return "Grey zone"
    return "Safe"


def scenario_z(z, disaster_dx: float, fx_dx: float, tot_dx: float = 0.0):
    """
    Apply active shocks to a baseline Z.

    The model is delta_Z = beta * delta_X: each *_dx argument is the change
    in that shock variable itself (e.g. a change in an exchange rate,
    LCU per US$), not a multiplier on some assumed "typical" shock size.
    """
    dz = 0.0
    if SHOCKS["disaster"]["active"]:
        dz += disaster_dx * SHOCKS["disaster"]["coef"]
    if SHOCKS["fx"]["active"]:
        dz += fx_dx * SHOCKS["fx"]["coef"]
    if SHOCKS["tot"]["active"]:
        dz += tot_dx * SHOCKS["tot"]["coef"]
    return z + dz


def active_shocks():
    """Shocks currently turned on in config, in a stable order."""
    order = ["disaster", "fx", "tot"]
    return [(key, SHOCKS[key]) for key in order if SHOCKS[key]["active"]]
