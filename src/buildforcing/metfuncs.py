'''
Meteorological functions for building forcing datasets.
'''
import numpy as np
from numpy.typing import NDArray

# Saturation vapor pressure over liquid water
def esat_liq(T: NDArray[np.floating]) -> NDArray[np.floating]:
    # Magnus formula - see Huang 2018
    # T in degC, esat in Pa
    return 610.94 * np.exp((17.625 * T) / (T + 243.04))  # in Pa

# Saturation vapor pressure over ice
def esat_ice(T: NDArray[np.floating]) -> NDArray[np.floating]:
    # Also from Huang 2018
    # T in degC, esat in Pa
    return 611.21 * np.exp((22.587 * T) / (T + 273.86))  # in Pa

# Specific humidity to vapor pressure
def q_to_e(q: NDArray[np.floating], p: NDArray[np.floating]) -> NDArray[np.floating]:
    # q in kg/kg, p in Pa, e in Pa
    # See downloaded list of formulas from "plymouth state"
    return (q * p) / (0.622 + 0.378 * q)

# Psychrometric constant
def psychro_const(p: NDArray[np.floating]) -> NDArray[np.floating]:
    # p in Pa, gamma in Pa/K
    cp = 1005.7  # J/(kg·K)
    Lv = 2.5e6  # J/kg
    epsilon = 0.622  # Rd/Rv
    return (cp * p) / (epsilon * Lv)  # in Pa/K

# Relative humidity from q and Tair
def rh_from_q_tair(q: NDArray[np.floating], Tair: NDArray[np.floating], p: NDArray[np.floating]) -> NDArray[np.floating]:
    # q in kg/kg, Tair in degC, p in Pa, rh in fraction
    e = q_to_e(q, p)
    esat = esat_liq(Tair)
    return e / esat  # fraction

# Vapor pressure from wet-bulb temperature
def e_from_wetbulb(Ta: NDArray[np.floating], Twb: NDArray[np.floating], p: NDArray[np.floating]) -> NDArray[np.floating]:
    # Twb in degC, p in Pa, e in Pa
    # Use np.where to handle both scalars and arrays
    esat = np.where(Twb < 0, esat_ice(Twb), esat_liq(Twb))
    gamma = psychro_const(p)
    return esat - gamma * (Ta - Twb)  # in Pa

# Wet-bulb temperature from Ta, q, p
def calculate_wetbulb(Ta_c: NDArray[np.floating], q: NDArray[np.floating], p_pa: NDArray[np.floating]) -> NDArray[np.floating]:
    # Ta in degC, q in kg/kg, p in Pa
    # Returns Twb in degC
    e = q_to_e(q, p_pa)  # in Pa
    gamma = psychro_const(p_pa)  # in Pa/K

    # Initial guess for Twb (vectorized)
    Tmax = Ta_c.copy()
    Tmin = Ta_c - 40.0  # Assume wet-bulb won't be lower than 40C below air temp
    Twb = Tmin.copy()  # Just to initialize

    # Iterative solution based on e_from_wetbulb (vectorized bisection)
    for _ in range(100):
        Twb = (Tmax + Tmin) / 2.0  # Midpoint estimate

        e_calc = e_from_wetbulb(Ta_c, Twb, p_pa)
        error = e - e_calc

        # Check convergence - continue if any element hasn't converged
        if np.all(np.abs(error) < 0.01):
            break

        # Update bounds (vectorized with np.where)
        # If error > 0: Twb is too low, raise Tmin
        # If error <= 0: Twb is too high, lower Tmax
        Tmin = np.where(error > 0, Twb, Tmin)
        Tmax = np.where(error <= 0, Twb, Tmax)

    # Check if final Twb is > Ta (vectorized check)
    if np.any(Twb > Ta_c):
        raise ValueError("Calculated wet-bulb temperature is greater than air temperature.")

    return Twb

# Wang 2019 snowfall partition function
def wang2019_snowfrac(Twb: NDArray[np.floating]) -> NDArray[np.floating]:
    # Equation coefficients
    a = 6.99e-5
    b = 2.0
    c = 3.97

    return 1.0 / (1.0 + a * np.exp(b*(Twb + c)))

def jordan_snowfrac(T: NDArray[np.floating]) -> NDArray[np.floating]:
    '''
    Partition precip using method of Jordan 1991 as described in Wang 2019
    Note that NCAR NOAH-MP docs appear to have typo, while Wang makes more sense.
    Implementation here matches Wang picture.
    
    :param T: Air temperature in K

    returns fraction snow
    '''
    # Change to degrees C
    Tc = T - 273.15

    # Calculate linear section first
    fSnow = -0.2*Tc + 1

    # Set sections outside of linear
    fSnow[Tc < 0.5] = 1
    fSnow[(Tc > 2) & (Tc < 2.5)] = 0.6
    fSnow[Tc > 2.5] = 0
    
    return fSnow