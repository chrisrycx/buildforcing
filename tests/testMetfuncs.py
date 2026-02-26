"""Unit tests for metfuncs.py functions with numpy arrays"""
import numpy as np
import unittest

from buildforcing.metfuncs import (
    esat_liq, esat_ice, q_to_e, psychro_const,
    rh_from_q_tair, e_from_wetbulb, calculate_wetbulb,
    wang2019_snowfrac, jordan_snowfrac
)


class TestEsatLiq(unittest.TestCase):
    def test_array_input_output(self):
        """Test that esat_liq accepts and returns numpy arrays"""
        T_array = np.array([0.0, 10.0, 20.0, 30.0])
        result = esat_liq(T_array)
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.shape, T_array.shape)
        self.assertTrue(result.dtype == np.float64 or np.issubdtype(result.dtype, np.floating))

    def test_positive_output(self):
        """Test that saturation vapor pressure is positive"""
        T_array = np.array([-10.0, 0.0, 10.0, 20.0])
        result = esat_liq(T_array)
        self.assertTrue(np.all(result > 0))


class TestEsatIce(unittest.TestCase):
    def test_array_input_output(self):
        """Test that esat_ice accepts and returns numpy arrays"""
        T_array = np.array([-20.0, -10.0, 0.0, 10.0])
        result = esat_ice(T_array)
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.shape, T_array.shape)
        self.assertTrue(result.dtype == np.float64 or np.issubdtype(result.dtype, np.floating))

    def test_positive_output(self):
        """Test that saturation vapor pressure is positive"""
        T_array = np.array([-30.0, -20.0, -10.0, 0.0])
        result = esat_ice(T_array)
        self.assertTrue(np.all(result > 0))


class TestQToE(unittest.TestCase):
    def test_array_input_output(self):
        """Test that q_to_e accepts and returns numpy arrays"""
        q_array = np.array([0.001, 0.005, 0.010, 0.015])
        p_array = np.array([101325.0, 101325.0, 101325.0, 101325.0])
        result = q_to_e(q_array, p_array)
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.shape, q_array.shape)
        self.assertTrue(result.dtype == np.float64 or np.issubdtype(result.dtype, np.floating))

    def test_positive_output(self):
        """Test that vapor pressure is positive"""
        q_array = np.array([0.001, 0.005, 0.010])
        p_array = np.array([101325.0, 101325.0, 101325.0])
        result = q_to_e(q_array, p_array)
        self.assertTrue(np.all(result > 0))


class TestPsychroConst(unittest.TestCase):
    def test_array_input_output(self):
        """Test that psychro_const accepts and returns numpy arrays"""
        p_array = np.array([90000.0, 95000.0, 101325.0, 105000.0])
        result = psychro_const(p_array)
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.shape, p_array.shape)
        self.assertTrue(result.dtype == np.float64 or np.issubdtype(result.dtype, np.floating))

    def test_positive_output(self):
        """Test that psychrometric constant is positive"""
        p_array = np.array([90000.0, 101325.0, 110000.0])
        result = psychro_const(p_array)
        self.assertTrue(np.all(result > 0))


class TestRhFromQTair(unittest.TestCase):
    def test_array_input_output(self):
        """Test that rh_from_q_tair accepts and returns numpy arrays"""
        q_array = np.array([0.001, 0.005, 0.010, 0.015])
        T_array = np.array([0.0, 10.0, 20.0, 30.0])
        p_array = np.array([101325.0, 101325.0, 101325.0, 101325.0])
        result = rh_from_q_tair(q_array, T_array, p_array)
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.shape, q_array.shape)
        self.assertTrue(result.dtype == np.float64 or np.issubdtype(result.dtype, np.floating))

    def test_rh_range(self):
        """Test that relative humidity is in valid range"""
        q_array = np.array([0.001, 0.005, 0.010])
        T_array = np.array([10.0, 20.0, 30.0])
        p_array = np.array([101325.0, 101325.0, 101325.0])
        result = rh_from_q_tair(q_array, T_array, p_array)
        self.assertTrue(np.all(result >= 0))
        self.assertTrue(np.all(result <= 1.0))


class TestEFromWetbulb(unittest.TestCase):
    def test_array_input_output(self):
        """Test that e_from_wetbulb accepts and returns numpy arrays"""
        Ta_array = np.array([5.0, 10.0, 15.0, 20.0])
        Twb_array = np.array([2.0, 5.0, 10.0, 15.0])
        p_array = np.array([101325.0, 101325.0, 101325.0, 101325.0])
        result = e_from_wetbulb(Ta_array, Twb_array, p_array)
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.shape, Ta_array.shape)
        self.assertTrue(result.dtype == np.float64 or np.issubdtype(result.dtype, np.floating))

    def test_handles_negative_temperatures(self):
        """Test that function handles negative wet-bulb temperatures (ice)"""
        Ta_array = np.array([5.0, 0.0, -5.0])
        Twb_array = np.array([-2.0, -5.0, -10.0])
        p_array = np.array([101325.0, 101325.0, 101325.0])
        result = e_from_wetbulb(Ta_array, Twb_array, p_array)
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.shape, Ta_array.shape)


class TestCalculateWetbulb(unittest.TestCase):
    def test_array_input_output(self):
        """Test that calculate_wetbulb accepts and returns numpy arrays"""
        Ta_array = np.array([10.0, 15.0, 20.0, 25.0])
        q_array = np.array([0.003, 0.005, 0.008, 0.010])
        p_array = np.array([101325.0, 101325.0, 101325.0, 101325.0])
        result = calculate_wetbulb(Ta_array, q_array, p_array)
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.shape, Ta_array.shape)
        self.assertTrue(result.dtype == np.float64 or np.issubdtype(result.dtype, np.floating))

    def test_wetbulb_less_than_air_temp(self):
        """Test that wet-bulb temperature is less than or equal to air temperature"""
        Ta_array = np.array([15.0, 20.0, 25.0])
        q_array = np.array([0.005, 0.008, 0.010])
        p_array = np.array([101325.0, 101325.0, 101325.0])
        result = calculate_wetbulb(Ta_array, q_array, p_array)
        self.assertTrue(np.all(result <= Ta_array))


class TestWang2019Snowfrac(unittest.TestCase):
    def test_array_input_output(self):
        """Test that wang2019_snowfrac accepts and returns numpy arrays"""
        Twb_array = np.array([-5.0, -2.0, 0.0, 2.0, 5.0])
        result = wang2019_snowfrac(Twb_array)
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.shape, Twb_array.shape)
        self.assertTrue(result.dtype == np.float64 or np.issubdtype(result.dtype, np.floating))

    def test_snow_fraction_range(self):
        """Test that snow fraction is between 0 and 1"""
        Twb_array = np.array([-10.0, -5.0, 0.0, 5.0, 10.0])
        result = wang2019_snowfrac(Twb_array)
        self.assertTrue(np.all(result >= 0))
        self.assertTrue(np.all(result <= 1))

    def test_snow_fraction_decreases_with_temp(self):
        """Test that snow fraction decreases as wet-bulb temperature increases"""
        Twb_array = np.array([-5.0, 0.0, 5.0])
        result = wang2019_snowfrac(Twb_array)
        # Should be monotonically decreasing
        self.assertTrue(result[0] > result[1] > result[2])


class TestJordanSnowfrac(unittest.TestCase):
    def test_temperature_range_minus1_to_5C(self):
        """Test jordan_snowfrac with temperatures from -1 to 5°C at 0.5°C resolution"""
        # Create array from -1 to 5°C with 0.5°C resolution
        T_celsius = np.arange(-1.0, 5.5, 0.5)
        # Convert to Kelvin
        T_kelvin = T_celsius + 273.15

        result = jordan_snowfrac(T_kelvin)

        # Verify output is numpy array
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.shape, T_kelvin.shape)

        # Expected values based on Jordan 1991 method:
        # T < 0.5°C: fSnow = 1.0
        # 0.5°C ≤ T ≤ 2°C: fSnow = -0.2*T + 1 (linear)
        # 2°C < T < 2.5°C: fSnow = 0.6
        # 2.5°C: fSnow = -0.2*2.5 + 1 = 0.5 (still in linear region)
        # T > 2.5°C: fSnow = 0.0

        expected = np.array([
            1.0,    # -1.0°C: < 0.5, all snow
            1.0,    # -0.5°C: < 0.5, all snow
            1.0,    # 0.0°C: < 0.5, all snow
            0.9,    # 0.5°C: -0.2*0.5 + 1 = 0.9
            0.8,    # 1.0°C: -0.2*1.0 + 1 = 0.8
            0.7,    # 1.5°C: -0.2*1.5 + 1 = 0.7
            0.6,    # 2.0°C: -0.2*2.0 + 1 = 0.6
            0.5,    # 2.5°C: -0.2*2.5 + 1 = 0.5 (linear formula applies)
            0.0,    # 3.0°C: > 2.5, no snow
            0.0,    # 3.5°C: > 2.5, no snow
            0.0,    # 4.0°C: > 2.5, no snow
            0.0,    # 4.5°C: > 2.5, no snow
            0.0,    # 5.0°C: > 2.5, no snow
        ])

        # Test all values are between 0 and 1
        self.assertTrue(np.all(result >= 0))
        self.assertTrue(np.all(result <= 1))

        # Test expected values with small tolerance for floating point
        np.testing.assert_allclose(result, expected, rtol=1e-10, atol=1e-10)

    def test_boundary_conditions(self):
        """Test jordan_snowfrac at specific boundary temperatures"""
        # Test key boundary points
        T_celsius = np.array([0.5, 2.0, 2.5, 3.0])
        T_kelvin = T_celsius + 273.15

        result = jordan_snowfrac(T_kelvin)

        # At 0.5°C: start of linear region, fSnow = -0.2*0.5 + 1 = 0.9
        self.assertAlmostEqual(result[0], 0.9, places=10)

        # At 2.0°C: end of main linear region, fSnow = -0.2*2.0 + 1 = 0.6
        self.assertAlmostEqual(result[1], 0.6, places=10)

        # At 2.5°C: linear formula still applies, fSnow = -0.2*2.5 + 1 = 0.5
        self.assertAlmostEqual(result[2], 0.5, places=10)

        # At 3.0°C: T > 2.5, so fSnow = 0
        self.assertAlmostEqual(result[3], 0.0, places=10)

    def compare_wang_jordan(self):
        '''
        Based on the wang 2019 paper, there are some situations
        where Jordan has a higher fraction than Wang. Verify
        '''
        Tc = [0.5,1,1.5,1.5,2.5,4]
        rh = [100,95,80,70,50,60]
        wang_higher = [0,0,1,1,1,1]



if __name__ == '__main__':
    unittest.main()
