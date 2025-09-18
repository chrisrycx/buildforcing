'''
Unit tests for the snotelQC module
'''

import unittest
import numpy as np
import pandas as pd
from buildforcing.snotelQC import check_outliers, qc_maxmin_temperatures, fill_T_nldas


class TestCheckOutliers(unittest.TestCase):
    def test_no_outliers(self):
        # Test with normal distribution data - should have no outliers with 3 sigma
        data = np.array([1, 2, 3, 4, 5])
        result = check_outliers(data, sigma_threshold=3.0)
        self.assertFalse(result.any())

    def test_with_outliers(self):
        # Test with clear outliers
        data = np.array([1, 2, 3, 4, 100])  # 100 is clearly an outlier
        result = check_outliers(data, sigma_threshold=2.0)
        self.assertTrue(result[-1])  # Last element should be flagged as outlier
        self.assertFalse(result[:-1].any())  # First elements should not be outliers

    def test_custom_sigma_threshold(self):
        # Test with different sigma thresholds
        data = np.array([0, 1, 2, 3, 4, 10])
        result_strict = check_outliers(data, sigma_threshold=1.0)
        result_loose = check_outliers(data, sigma_threshold=3.0)
        # Strict threshold should flag more outliers than loose threshold
        self.assertGreaterEqual(result_strict.sum(), result_loose.sum())

    def test_symmetric_outliers(self):
        # Test with both high and low outliers
        data = np.array([-50, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 3.5, 2.7, 4.2, 50])
        result = check_outliers(data, sigma_threshold=2.0)
        self.assertTrue(result[0])  # First element (-50) should be outlier
        self.assertTrue(result[-1])  # Last element (50) should be outlier
        self.assertFalse(result[1:-1].any())  # Middle elements should not be outliers

    def test_empty_array(self):
        # Test with empty array
        data = np.array([])
        result = check_outliers(data)
        self.assertEqual(len(result), 0)

    def test_single_value(self):
        # Test with single value - should not be an outlier
        data = np.array([5])
        result = check_outliers(data)
        self.assertFalse(result[0])


class TestQCMaxminTemperatures(unittest.TestCase):
    def setUp(self):
        # Create sample temperature data for testing
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        self.normal_df = pd.DataFrame({
            'Tmax': np.random.normal(20, 5, 100),
            'Tmin': np.random.normal(10, 3, 100)
        }, index=dates)

        # Ensure Tmax > Tmin for normal data
        self.normal_df['Tmin'] = np.minimum(self.normal_df['Tmin'], self.normal_df['Tmax'] - 1)

    def test_normal_data(self):
        # Test with normal temperature data
        result = qc_maxmin_temperatures(self.normal_df)
        self.assertIn('Tmax_bad', result.columns)
        self.assertIn('Tmin_bad', result.columns)
        self.assertEqual(len(result), len(self.normal_df))
        # Most data should be good
        self.assertLess(result['Tmax_bad'].sum(), len(result) * 0.1)
        self.assertLess(result['Tmin_bad'].sum(), len(result) * 0.1)

    def test_inconsistent_maxmin(self):
        # Test with Tmin > Tmax (inconsistent)
        df = self.normal_df.copy()
        df.iloc[0, df.columns.get_loc('Tmax')] = 5  # Tmax = 5
        df.iloc[0, df.columns.get_loc('Tmin')] = 15  # Tmin = 15 (inconsistent)

        result = qc_maxmin_temperatures(df)
        self.assertTrue(result.iloc[0]['Tmax_bad'])
        self.assertTrue(result.iloc[0]['Tmin_bad'])

    def test_outlier_temperatures(self):
        # Test with extreme outlier temperatures
        df = self.normal_df.copy()
        df.iloc[0, df.columns.get_loc('Tmax')] = 200  # Extreme outlier
        df.iloc[1, df.columns.get_loc('Tmin')] = -100  # Extreme outlier

        result = qc_maxmin_temperatures(df)
        # Check that outliers are flagged   
        self.assertTrue(result.iloc[0]['Tmax_bad'])
        self.assertTrue(result.iloc[1]['Tmin_bad'])

    # def test_small_dataset_warning(self):
    #     # Test with dataset smaller than 365 days
    #     small_df = self.normal_df.head(50)
    #     with self.assertLogs(level='WARNING') as log:
    #         result = qc_maxmin_temperatures(small_df)
    #     # Should still return result
    #     self.assertEqual(len(result), 50)

    def test_column_names(self):
        # Test that function handles different column names correctly
        df = self.normal_df.copy()
        df.columns = ['temp_max', 'temp_min']
        result = qc_maxmin_temperatures(df)
        self.assertIn('Tmax_bad', result.columns)
        self.assertIn('Tmin_bad', result.columns)


class TestFillTNldas(unittest.TestCase):
    def setUp(self):
        # Create sample SNOTEL data with gaps
        dates = pd.date_range('2023-01-01', periods=30, freq='D', tz='MST')
        self.snotel_tmax = pd.Series(
            np.random.normal(20, 5, 30),
            index=dates,
            name='T_max_C'
        )
        self.snotel_tmin = pd.Series(
            np.random.normal(10, 3, 30),
            index=dates,
            name='T_min_C'
        )

        # Create gaps in SNOTEL data
        self.snotel_tmax.iloc[5:10] = np.nan
        self.snotel_tmin.iloc[15:20] = np.nan

        # Create hourly NLDAS data in UTC and Kelvin
        nldas_dates = pd.date_range('2023-01-01', periods=30*24, freq='H', tz='UTC')
        # Simulate hourly temperature variations
        daily_temp = np.repeat(np.random.normal(293, 5, 30), 24)  # Base temp in Kelvin
        hourly_variation = np.tile(np.sin(np.linspace(0, 2*np.pi, 24)) * 5, 30)
        self.nldas_tmax_data = pd.Series(
            daily_temp + hourly_variation + 5,  # Slightly higher for max
            index=nldas_dates
        )
        self.nldas_tmin_data = pd.Series(
            daily_temp + hourly_variation - 5,  # Slightly lower for min
            index=nldas_dates
        )

    def test_fill_tmax_data(self):
        # Test filling Tmax data
        result = fill_T_nldas(self.snotel_tmax, self.nldas_tmax_data)

        self.assertIn('T_max_C', result.columns)
        self.assertIn('filled_flag', result.columns)
        self.assertEqual(len(result), len(self.snotel_tmax))

        # Check that gaps were filled
        self.assertFalse(result['T_max_C'].isna().any())

        # Check that filled_flag correctly identifies filled values
        original_gaps = self.snotel_tmax.isna()
        np.testing.assert_array_equal(result['filled_flag'], original_gaps)

    def test_fill_tmin_data(self):
        # Test filling Tmin data
        result = fill_T_nldas(self.snotel_tmin, self.nldas_tmin_data)

        self.assertIn('T_min_C', result.columns)
        self.assertIn('filled_flag', result.columns)

        # Check that gaps were filled
        self.assertFalse(result['T_min_C'].isna().any())

    def test_invalid_column_name(self):
        # Test with invalid SNOTEL column name
        invalid_snotel = self.snotel_tmax.copy()
        invalid_snotel.name = 'invalid_name'

        with self.assertRaises(ValueError):
            fill_T_nldas(invalid_snotel, self.nldas_tmax_data)

    def test_no_gaps_to_fill(self):
        # Test with SNOTEL data that has no gaps
        dates = pd.date_range('2023-01-01', periods=30, freq='D', tz='MST')
        complete_snotel = pd.Series(
            np.random.normal(20, 5, 30),
            index=dates,
            name='T_max_C'
        )
        result = fill_T_nldas(complete_snotel, self.nldas_tmax_data)

        # Should return original data with all filled_flag as False
        pd.testing.assert_series_equal(result['T_max_C'], complete_snotel)
        self.assertFalse(result['filled_flag'].any())

    def test_kelvin_to_celsius_conversion(self):
        # Test that NLDAS data is properly converted from Kelvin to Celsius
        result = fill_T_nldas(self.snotel_tmax, self.nldas_tmax_data)

        # Filled values should be in reasonable Celsius range (not Kelvin range)
        filled_values = result.loc[result['filled_flag'], 'T_max_C']
        if len(filled_values) > 0:
            self.assertTrue((filled_values < 100).all())  # Should be in Celsius, not Kelvin
            self.assertTrue((filled_values > -50).all())  # Reasonable temperature range


if __name__ == '__main__':
    unittest.main()