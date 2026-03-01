"""Unit tests for the CO2 heat pump thermodynamic cycle calculations."""

import math
import unittest

from co2_cycle import (
    state_from_pt,
    state_after_throttle,
    compute_cycle,
    compute_compressor_metrics,
    get_saturation_envelope,
)


class TestStateFromPT(unittest.TestCase):
    """Test computing thermodynamic state from pressure and temperature."""

    def test_returns_expected_keys(self):
        state = state_from_pt(35.0, 5.0)
        for key in ("P", "T", "P_bar", "T_C", "h", "s", "rho"):
            self.assertIn(key, state)

    def test_unit_conversions(self):
        state = state_from_pt(50.0, 20.0)
        self.assertAlmostEqual(state["P"], 50.0e5, places=0)
        self.assertAlmostEqual(state["T"], 293.15, places=2)
        self.assertEqual(state["P_bar"], 50.0)
        self.assertEqual(state["T_C"], 20.0)

    def test_enthalpy_positive(self):
        state = state_from_pt(35.0, 5.0)
        self.assertGreater(state["h"], 0)

    def test_entropy_positive(self):
        state = state_from_pt(35.0, 5.0)
        self.assertGreater(state["s"], 0)

    def test_density_positive(self):
        state = state_from_pt(35.0, 5.0)
        self.assertGreater(state["rho"], 0)

    def test_supercritical_state(self):
        """State above critical pressure (~73.8 bar) should still compute."""
        state = state_from_pt(100.0, 90.0)
        self.assertGreater(state["h"], 0)
        self.assertGreater(state["rho"], 0)


class TestStateAfterThrottle(unittest.TestCase):
    """Test isenthalpic throttle expansion."""

    def test_enthalpy_preserved(self):
        """h should be the same before and after throttle."""
        s3 = state_from_pt(100.0, 35.0)
        s4 = state_after_throttle(35.0, s3["h"])
        self.assertAlmostEqual(s4["h"], s3["h"], places=1)

    def test_two_phase_quality(self):
        """After throttling to low pressure, quality should be between 0-1."""
        s3 = state_from_pt(100.0, 35.0)
        s4 = state_after_throttle(35.0, s3["h"])
        self.assertIn("Q", s4)
        self.assertGreater(s4["Q"], 0.0)
        self.assertLess(s4["Q"], 1.0)

    def test_temperature_is_saturation(self):
        """After throttling to subcritical pressure, T should be sat. temp."""
        import CoolProp.CoolProp as CP
        P4_bar = 35.0
        T_sat = CP.PropsSI("T", "P", P4_bar * 1e5, "Q", 0, "CO2")
        s3 = state_from_pt(100.0, 35.0)
        s4 = state_after_throttle(P4_bar, s3["h"])
        self.assertAlmostEqual(s4["T"], T_sat, delta=0.5)


class TestComputeCycle(unittest.TestCase):
    """Test the full cycle computation."""

    def setUp(self):
        self.cycle = compute_cycle(
            P1_bar=35.0, T1_C=5.0,
            P2_bar=100.0, T2_C=90.0,
            P3_bar=100.0, T3_C=35.0,
            P4_bar=35.0,
        )

    def test_four_states(self):
        self.assertEqual(len(self.cycle["states"]), 4)

    def test_compressor_work_positive(self):
        """Compressor requires positive work input."""
        self.assertGreater(self.cycle["w_comp"], 0)

    def test_gas_cooler_heat_positive(self):
        """Gas cooler rejects heat (positive q_gc)."""
        self.assertGreater(self.cycle["q_gc"], 0)

    def test_evaporator_heat_positive(self):
        """Evaporator absorbs heat (positive q_evap)."""
        self.assertGreater(self.cycle["q_evap"], 0)

    def test_energy_balance(self):
        """w_comp + q_evap ≈ q_gc (first-law energy balance)."""
        balance = self.cycle["w_comp"] + self.cycle["q_evap"]
        self.assertAlmostEqual(balance, self.cycle["q_gc"],
                               delta=self.cycle["q_gc"] * 0.01)

    def test_cop_heating_reasonable(self):
        """Heating COP should be > 1 for a heat pump."""
        self.assertGreater(self.cycle["cop_heating"], 1.0)
        self.assertLess(self.cycle["cop_heating"], 15.0)

    def test_cop_cooling_reasonable(self):
        """Cooling COP should be positive."""
        self.assertGreater(self.cycle["cop_cooling"], 0.0)

    def test_state4_enthalpy_equals_state3(self):
        """Isenthalpic throttle: h4 == h3."""
        s3 = self.cycle["states"][2]
        s4 = self.cycle["states"][3]
        self.assertAlmostEqual(s3["h"], s4["h"], places=1)


class TestCompressorMetrics(unittest.TestCase):
    """Test compressor-related performance calculations."""

    def setUp(self):
        self.cycle = compute_cycle(35.0, 5.0, 100.0, 90.0, 100.0, 35.0, 35.0)
        self.comp = compute_compressor_metrics(
            self.cycle, displacement_m3h=10.0, stroke_volume_m3=0.001
        )

    def test_mass_flow_positive(self):
        self.assertGreater(self.comp["mass_flow"], 0)

    def test_heating_capacity_positive(self):
        self.assertGreater(self.comp["heating_capacity"], 0)

    def test_compressor_power_positive(self):
        self.assertGreater(self.comp["compressor_power"], 0)

    def test_rpm_positive(self):
        self.assertGreater(self.comp["rpm"], 0)

    def test_capacity_relation(self):
        """Heating capacity = cooling capacity + compressor power."""
        total = self.comp["cooling_capacity"] + self.comp["compressor_power"]
        self.assertAlmostEqual(total, self.comp["heating_capacity"],
                               delta=self.comp["heating_capacity"] * 0.01)


class TestSaturationEnvelope(unittest.TestCase):
    """Test saturation dome data generation."""

    def test_non_empty(self):
        env = get_saturation_envelope()
        self.assertGreater(len(env["h_f"]), 50)
        self.assertGreater(len(env["h_g"]), 50)

    def test_liquid_enthalpy_less_than_vapor(self):
        env = get_saturation_envelope()
        for hf, hg in zip(env["h_f"], env["h_g"]):
            self.assertLess(hf, hg)


if __name__ == "__main__":
    unittest.main()
