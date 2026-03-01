"""
Thermodynamic calculations for a CO2 heat pump cycle.

The cycle consists of four state points:
  1 - Compressor inlet (suction)
  2 - Compressor outlet (discharge)
  3 - Gas cooler outlet / before throttle valve
  4 - After throttle valve / evaporator inlet

Because CO2 heat pumps typically operate in a transcritical cycle,
the high-pressure side (states 2-3) is above the critical pressure,
while the low-pressure side (states 4-1) may be in the two-phase region.
"""

import CoolProp.CoolProp as CP
import numpy as np

FLUID = "CO2"


def state_from_pt(pressure_bar, temperature_c):
    """Compute full thermodynamic state from pressure and temperature.

    Parameters
    ----------
    pressure_bar : float
        Pressure in bar.
    temperature_c : float
        Temperature in degrees Celsius.

    Returns
    -------
    dict
        Dictionary with keys P (Pa), T (K), h (J/kg), s (J/(kg·K)),
        rho (kg/m³), and the original units P_bar and T_C.
    """
    P = pressure_bar * 1e5  # bar -> Pa
    T = temperature_c + 273.15  # °C -> K
    h = CP.PropsSI("H", "T", T, "P", P, FLUID)
    s = CP.PropsSI("S", "T", T, "P", P, FLUID)
    rho = CP.PropsSI("D", "T", T, "P", P, FLUID)
    return {
        "P": P, "T": T,
        "P_bar": pressure_bar, "T_C": temperature_c,
        "h": h, "s": s, "rho": rho,
    }


def state_after_throttle(pressure_bar, h_before):
    """Compute state after isenthalpic throttle valve.

    The throttle is isenthalpic, so h_4 = h_3.  After throttling to a
    sub-critical pressure the fluid is in the two-phase region; the
    temperature equals the saturation temperature at that pressure.

    Parameters
    ----------
    pressure_bar : float
        Pressure after the throttle valve in bar.
    h_before : float
        Enthalpy before the throttle valve (J/kg).

    Returns
    -------
    dict
        Thermodynamic state dictionary (same keys as state_from_pt, plus
        quality Q when in two-phase).
    """
    P = pressure_bar * 1e5
    h = h_before  # isenthalpic
    T = CP.PropsSI("T", "H", h, "P", P, FLUID)
    s = CP.PropsSI("S", "H", h, "P", P, FLUID)
    rho = CP.PropsSI("D", "H", h, "P", P, FLUID)

    # Check if we are in the two-phase region
    P_crit = CP.PropsSI("Pcrit", FLUID)
    result = {
        "P": P, "T": T,
        "P_bar": pressure_bar, "T_C": T - 273.15,
        "h": h, "s": s, "rho": rho,
    }
    if P < P_crit:
        h_f = CP.PropsSI("H", "P", P, "Q", 0, FLUID)
        h_g = CP.PropsSI("H", "P", P, "Q", 1, FLUID)
        if h_f <= h <= h_g:
            result["Q"] = (h - h_f) / (h_g - h_f)
    return result


def compute_cycle(P1_bar, T1_C, P2_bar, T2_C, P3_bar, T3_C, P4_bar):
    """Compute the full four-state CO2 heat pump cycle.

    Parameters
    ----------
    P1_bar, T1_C : float
        Pressure (bar) and temperature (°C) at compressor inlet.
    P2_bar, T2_C : float
        Pressure (bar) and temperature (°C) at compressor outlet.
    P3_bar, T3_C : float
        Pressure (bar) and temperature (°C) before throttle valve.
    P4_bar : float
        Pressure (bar) after the throttle valve.

    Returns
    -------
    dict
        Contains state dicts for points 1-4 and performance metrics.
    """
    s1 = state_from_pt(P1_bar, T1_C)
    s2 = state_from_pt(P2_bar, T2_C)
    s3 = state_from_pt(P3_bar, T3_C)
    s4 = state_after_throttle(P4_bar, s3["h"])

    # Specific work and heat (per kg of refrigerant)
    w_comp = s2["h"] - s1["h"]  # compressor work (J/kg)
    q_gc = s2["h"] - s3["h"]    # heat rejected in gas cooler (J/kg)
    q_evap = s1["h"] - s4["h"]  # heat absorbed in evaporator (J/kg)

    cop_heating = q_gc / w_comp if w_comp > 0 else float("inf")
    cop_cooling = q_evap / w_comp if w_comp > 0 else float("inf")

    return {
        "states": [s1, s2, s3, s4],
        "w_comp": w_comp,
        "q_gc": q_gc,
        "q_evap": q_evap,
        "cop_heating": cop_heating,
        "cop_cooling": cop_cooling,
    }


def compute_compressor_metrics(cycle, displacement_m3h, stroke_volume_m3):
    """Compute compressor-related performance metrics.

    Parameters
    ----------
    cycle : dict
        Output of compute_cycle.
    displacement_m3h : float
        Volumetric displacement of the compressor in m³/h.
    stroke_volume_m3 : float
        Volume of a single stroke in m³.  The compressor has 4 cylinders,
        so total swept volume per revolution is ``stroke_volume_m3 * 4``.

    Returns
    -------
    dict
        Compressor metrics: mass_flow (kg/s), heating_capacity (W),
        cooling_capacity (W), compressor_power (W), rpm.
    """
    s1 = cycle["states"][0]
    rho_suction = s1["rho"]  # density at suction (kg/m³)

    # Mass flow rate: displacement * suction density
    vol_flow_m3s = displacement_m3h / 3600.0  # m³/h -> m³/s
    mass_flow = vol_flow_m3s * rho_suction  # kg/s

    # RPM: displacement / (stroke_volume * number_of_cylinders)
    n_cylinders = 4
    if stroke_volume_m3 > 0:
        rpm = displacement_m3h / (stroke_volume_m3 * n_cylinders * 60)
    else:
        rpm = 0.0

    heating_cap = mass_flow * cycle["q_gc"]
    cooling_cap = mass_flow * cycle["q_evap"]
    comp_power = mass_flow * cycle["w_comp"]

    return {
        "mass_flow": mass_flow,
        "heating_capacity": heating_cap,
        "cooling_capacity": cooling_cap,
        "compressor_power": comp_power,
        "rpm": rpm,
        "vol_flow_m3s": vol_flow_m3s,
        "rho_suction": rho_suction,
    }


# ---------------------------------------------------------------------------
# Envelope / background curve helpers
# ---------------------------------------------------------------------------

def get_saturation_envelope():
    """Return saturation dome data for CO2 (for plotting).

    Returns
    -------
    dict with keys h_f, h_g, s_f, s_g, T_sat, P_sat (arrays).
    """
    T_crit = CP.PropsSI("Tcrit", FLUID)
    T_triple = CP.PropsSI("Ttriple", FLUID)
    temps = np.linspace(T_triple + 1, T_crit - 0.1, 200)

    h_f, h_g, s_f, s_g, P_sat = [], [], [], [], []
    for T in temps:
        try:
            P = CP.PropsSI("P", "T", T, "Q", 0, FLUID)
            hf = CP.PropsSI("H", "T", T, "Q", 0, FLUID)
            hg = CP.PropsSI("H", "T", T, "Q", 1, FLUID)
            sf = CP.PropsSI("S", "T", T, "Q", 0, FLUID)
            sg = CP.PropsSI("S", "T", T, "Q", 1, FLUID)
            h_f.append(hf)
            h_g.append(hg)
            s_f.append(sf)
            s_g.append(sg)
            P_sat.append(P)
        except Exception:
            continue

    T_sat = temps[:len(h_f)]
    return {
        "h_f": np.array(h_f), "h_g": np.array(h_g),
        "s_f": np.array(s_f), "s_g": np.array(s_g),
        "T_sat": np.array(T_sat), "P_sat": np.array(P_sat),
    }


def get_isotherms(pressures, T_values_C):
    """Generate isotherms for the P-h diagram.

    Parameters
    ----------
    pressures : array-like
        Pressure range in Pa.
    T_values_C : list of float
        Temperatures in °C for which to draw isotherms.

    Returns
    -------
    list of dict
        Each dict has keys P, h, T_C.
    """
    lines = []
    for Tc in T_values_C:
        T = Tc + 273.15
        hs, ps = [], []
        for P in pressures:
            try:
                h = CP.PropsSI("H", "T", T, "P", P, FLUID)
                hs.append(h)
                ps.append(P)
            except Exception:
                continue
        if hs:
            lines.append({"P": np.array(ps), "h": np.array(hs), "T_C": Tc})
    return lines


def get_isobars(temperatures_K, P_values_bar):
    """Generate isobars for the T-s diagram.

    Parameters
    ----------
    temperatures_K : array-like
        Temperature range in K.
    P_values_bar : list of float
        Pressures in bar for which to draw isobars.

    Returns
    -------
    list of dict
        Each dict has keys T, s, P_bar.
    """
    lines = []
    for Pb in P_values_bar:
        P = Pb * 1e5
        ss, ts = [], []
        for T in temperatures_K:
            try:
                s = CP.PropsSI("S", "T", T, "P", P, FLUID)
                ss.append(s)
                ts.append(T)
            except Exception:
                continue
        if ss:
            lines.append({"T": np.array(ts), "s": np.array(ss), "P_bar": Pb})
    return lines
