import unittest
import pandas as pd
import numpy as np
from zoneinfo import ZoneInfo
import os
from datetime import datetime, timedelta, timezone
from buildforcing.datasets import PNNLSnotel, siteNLDAS
from buildforcing.downscale import downscaleTairV1, downscaleTairV0, downscalePrecipV1, partitionPrecipV0

@unittest.skip('Older version will be removed')
class TestDownscaleTairV0(unittest.TestCase):
    def setUp(self):
        # Create sample NLDAS temperature data (in Kelvin)
        temps_C = [1, 2, 3, 1, 1, 0, 3, 3]  # This will be for two days, 4 values per day
        temps_C = temps_C * 2  # Repeat for total of 4 days data
        temps_K = [temp + 273.15 for temp in temps_C]  # Convert to Kelvin

        self.nldas_Tair_K = pd.Series(
            temps_K,
            index=pd.date_range("2023-01-01 07:00", periods=16, freq="6h", tz="UTC")
        )

        # Create sample SNOTEL max and min temperature data (in Celsius), contains a missing value
        self.snotel_Tmax_C = pd.Series(
            [4, 4, None, 4],
            index=pd.date_range("2023-01-01", periods=4, freq="D", tz=ZoneInfo("America/Denver"))
        )
        self.snotel_Tmin_C = pd.Series(
            [0, 1, None, 0],
            index=pd.date_range("2023-01-01", periods=4, freq="D", tz=ZoneInfo("America/Denver"))
        )

    def test_downscaleTair(self):
        '''
        Test the downscaling of temperature data without missing values.
        '''
        # Get the first two days of data. Use iloc because timezones are too confusing
        nldas_data = self.nldas_Tair_K.iloc[:8]
        snotel_Tmax = self.snotel_Tmax_C.iloc[:2]
        snotel_Tmin = self.snotel_Tmin_C.iloc[:2]

        # Call the function
        result = downscaleTairV0(nldas_data, snotel_Tmax, snotel_Tmin)

        # Assert the result is a pandas Series
        self.assertIsInstance(result, pd.Series)

        # Assert the result has the same index as the input NLDAS data
        self.assertTrue(result.index.equals(nldas_data.index))

        # Assert the result values are not NaN
        self.assertFalse(result.isna().any())

        # Expected result values
        expected_temp_C = [0,2,4,2,2,1,4,3]
        expected_temp_K = [temp + 273.15 for temp in expected_temp_C]
        expected_result = pd.Series(
            expected_temp_K,
            index=pd.date_range("2023-01-01 07:00", periods=8, freq="6h", tz="UTC")
        )

        # Assert each value within a tolerance
        for i in range(len(result)):
            self.assertAlmostEqual(result.iloc[i], expected_result.iloc[i], places=2)

    def test_missingday(self):
        '''
        Test handling of missing day in SNOTEL data.
        For V0 of this algorithm, I will just linearly interpolate the missing max/min values.
        '''
        result = downscaleTairV0(self.nldas_Tair_K, self.snotel_Tmax_C, self.snotel_Tmin_C)

        # Expected result values
        expected_temp_C = [0,2,4,2,2,1,4,3.25]+[0.5,2.25,4,1.666,1.333,0,4,3]
        expected_temp_K = [temp + 273.15 for temp in expected_temp_C]
        expected_result = pd.Series(
            expected_temp_K,
            index=pd.date_range("2023-01-01 07:00", periods=16, freq="6h", tz="UTC")
        )

        # Assert each value within a tolerance
        for i in range(len(result)):
            self.assertAlmostEqual(result.iloc[i], expected_result.iloc[i], places=2)

class TestDownscaleTairV1(unittest.TestCase):
    def setUp(self):
        # Create sample NLDAS temperature data (in Kelvin)
        temps_C = [1, 2, 3, 1, 1, 0, 3, 3]  # This will be for two days, 4 values per day
        temps_C = temps_C * 2  # Repeat for total of 4 days data
        temps_K = [temp + 273.15 for temp in temps_C]  # Convert to Kelvin

        self.nldas_Tair_K = pd.Series(
            temps_K,
            index=pd.date_range("2023-01-01 07:00", periods=16, freq="6h", tz="UTC")
        )

        # Create sample SNOTEL max and min temperature data (in Celsius), contains a missing value
        self.snotel_Tmax_C = pd.Series(
            [4, 4, None, 4],
            index=pd.date_range("2023-01-01", periods=4, freq="D", tz=ZoneInfo("America/Denver"))
        )
        self.snotel_Tmin_C = pd.Series(
            [0, 1, None, 0],
            index=pd.date_range("2023-01-01", periods=4, freq="D", tz=ZoneInfo("America/Denver"))
        )

    def test_downscaleTair(self):
        '''
        Test the downscaling of temperature data without missing values.
        '''
        # Get the first two days of data. Use iloc because timezones are too confusing
        nldas_data = self.nldas_Tair_K.iloc[:8]
        snotel_Tmax = self.snotel_Tmax_C.iloc[:2]
        snotel_Tmin = self.snotel_Tmin_C.iloc[:2]

        # Call the function
        result = downscaleTairV1(nldas_data, snotel_Tmax, snotel_Tmin)

        # Assert the result is a pandas Series
        self.assertIsInstance(result, pd.Series)

        # Assert the result has the same index as the input NLDAS data
        self.assertTrue(result.index.equals(nldas_data.index))

        # Assert the result values are not NaN
        self.assertFalse(result.isna().any())

        # Expected result values
        expected_temp_C = [0,2,4,0,2,1,4,4]
        expected_temp_K = [temp + 273.15 for temp in expected_temp_C]
        expected_result = pd.Series(
            expected_temp_K,
            index=pd.date_range("2023-01-01 07:00", periods=8, freq="6h", tz="UTC")
        )

        # Assert each value within a tolerance
        for i in range(len(result)):
            self.assertAlmostEqual(result.iloc[i], expected_result.iloc[i], places=2)

    def test_missingday(self):
        '''
        Test handling of missing day in SNOTEL data.
        For V0 of this algorithm, I will just linearly interpolate the missing max/min values.
        '''
        result = downscaleTairV1(self.nldas_Tair_K, self.snotel_Tmax_C, self.snotel_Tmin_C)

        # Expected result values
        expected_temp_C = [0,2,4,0,2,1,4,4,0.5,2.25,4,0.5,1.33,0,4,4]
        expected_temp_K = [temp + 273.15 for temp in expected_temp_C]
        expected_result = pd.Series(
            expected_temp_K,
            index=pd.date_range("2023-01-01 07:00", periods=16, freq="6h", tz="UTC")
        )

        # Assert each value within a tolerance
        for i in range(len(result)):
            print(f"Result C: {result.iloc[i] - 273.15}, Expected C: {expected_result.iloc[i] - 273.15}")
            self.assertAlmostEqual(result.iloc[i], expected_result.iloc[i], places=2)

    def test_missing2days(self):
        '''
        Test handling of two missing days in SNOTEL data.
        This should throw an error because the I am limiting the interpolation to one day.
        '''
        snotel_missing = self.snotel_Tmax_C.copy()
        snotel_missing.iloc[1] = None
        with self.assertRaises(ValueError):
            downscaleTairV1(self.nldas_Tair_K, snotel_missing, self.snotel_Tmin_C)

class TestdownscalePrecipV1(unittest.TestCase):
    def setUp(self):
        # Run a test using some actual data
        self.snotel = PNNLSnotel('Quemazon', os.environ['SNOTEL_PATH'])
        self.snotel.load_data()
        self.snotel_precip = self.snotel.data.loc['2016-01-01':'2019-12-31','precip_mm']  # Should contain a gap

    def test_input_date_range(self):
        '''
        Test the input date range for the downscaling function.
        '''
        nldas = siteNLDAS(self.snotel.latitude, self.snotel.longitude, start_date=datetime(2016,1,1,0), end_date=datetime(2019,12,31,23))
        nldas.loadNetCDF(os.environ['NLDAS_PATH'])
        nldas_precip = nldas.data['Rainf']

        # Verify that there is a value error when NLDAS data is outside SNOTEL range
        # Note: NLDAS in this function will be outside the snotel range after the timezone conversion
        with self.assertRaises(ValueError):
            downscalePrecipV1(nldas_precip, self.snotel_precip)
     

    def test_downscalePrecipV1(self):

        nldas = siteNLDAS(self.snotel.latitude, self.snotel.longitude, start_date=datetime(2016,1,2,0), end_date=datetime(2019,12,30,23))
        nldas.loadNetCDF(os.environ['NLDAS_PATH'])
        nldas_precip = nldas.data['Rainf']

        nldas_corrected = downscalePrecipV1(nldas_precip, self.snotel_precip)

        # Verify index is in UTC
        self.assertEqual(nldas_corrected.index.tz, timezone.utc)
        
        # Verify output does not have NaNs
        self.assertFalse(nldas_corrected.isna().any())

        # Verify sum of 2016 precip is close to SNOTEL
        snotel_2016_sum = self.snotel_precip.loc['2016'].sum()
        nldas_2016_sum = nldas_corrected.loc['2016'].sum()
        self.assertAlmostEqual(snotel_2016_sum, nldas_2016_sum, delta=1)

        # Verify total precip in 2018, where SNOTEL data is missing, is similar to total in 2019
        nldas_2018_sum = nldas_corrected.loc['2018'].sum()
        nldas_2019_sum = nldas_corrected.loc['2019'].sum()
        self.assertAlmostEqual(nldas_2018_sum, nldas_2019_sum, delta=nldas_2019_sum*0.2)  # Allow 20% difference

        


class TestpartitionPrecipV0(unittest.TestCase):
    def setUp(self):
        # Create a dummy precipitation dataset (4 days with hourly data)
        self.precip_mm = pd.Series(
            [1,2,3,4,5,6,7,8,1,2,3,4,5,6,7,8],
            index=pd.date_range("2023-01-01 00:00", periods=16, freq="6h", tz="UTC")
        )

        # Create an array of temperatures (in Kelvin) for the same period
        temps_K = np.array([1, 2, -1, 1, 1, 0, 3, -5] * 2)
        temps_K = temps_K + 273.15  # Convert to Kelvin
        self.temps_K = pd.Series(
            temps_K,
            index=pd.date_range("2023-01-01 00:00", periods=16, freq="6h", tz="UTC")
        )

    def test_partitionPrecipV0(self):
        '''
        Test the partitioning of precipitation data based on temperature thresholds.
        '''
        # Expected arrays for rain and snow
        expected_snow = np.array([0, 0, 3, 0, 0, 0, 0, 8] * 2)
        expected_rain = np.array([1, 2, 0, 4, 5, 6, 7, 0] * 2)
        
        # Call the function
        precip_partitioned = partitionPrecipV0(self.precip_mm, self.temps_K)
        rain = precip_partitioned['rain_mm']
        snow = precip_partitioned['snow_mm']

        # Assert the result is a pandas Series
        self.assertIsInstance(rain, pd.Series)
        self.assertIsInstance(snow, pd.Series)

        # Assert the result has the same index as the input NLDAS data
        self.assertTrue(rain.index.equals(self.precip_mm.index))
        self.assertTrue(snow.index.equals(self.precip_mm.index))

        # Assert that the expected values match the actual values
        np.testing.assert_array_almost_equal(rain.values, expected_rain, decimal=2)
        np.testing.assert_array_almost_equal(snow.values, expected_snow, decimal=2)


if __name__ == "__main__":
    unittest.main()