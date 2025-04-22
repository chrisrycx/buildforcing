import unittest
import pandas as pd
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from buildforcing.downscale import downscaleTair, downscalePrecip

class TestDownscaleTair(unittest.TestCase):
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
        result = downscaleTair(nldas_data, snotel_Tmax, snotel_Tmin)

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
        result = downscaleTair(self.nldas_Tair_K, self.snotel_Tmax_C, self.snotel_Tmin_C)

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

class TestDownscalePrecip(unittest.TestCase):
    def setUp(self):
        # Create a dummy precipitation dataset (4 days with hourly data)
        self.precip_mm = pd.Series(
            [1,2,3,4,5,6,7,8,1,2,3,4,5,6,7,8],
            index=pd.date_range("2023-01-01 00:00", periods=16, freq="6h", tz="UTC")
        )

        # Resample to hourly data
        self.precip_mm = self.precip_mm.resample("1h").ffill()

        # 4 days of SNOTEL data (daily data), first day will be doubled, second day will be halved, third day will be missing, fourth day will be zero
        self.snotel_mm = pd.Series(
            [20,13,None,0],
            index=pd.date_range("2023-01-01 00:00", periods=4, freq="24h", tz="UTC")
        )
    
    def test_scaling(self):
        '''
        Test that the data is scaled correctly by just looking at the first two days.
        '''
        # By my calculation, the first day total precip should be 60 
        rescaled = downscalePrecip(self.precip_mm['2023-01-01':'2023-01-02 23:00'], self.snotel_mm['2023-01-01':'2023-01-02 18:00'])

        # Assert the result is a pandas Series
        self.assertIsInstance(rescaled, pd.Series)

        # Assert the result has the same index as the input NLDAS data
        self.assertTrue(rescaled.index.equals(self.precip_mm['2023-01-01':'2023-01-02 23:00'].index))

        # Spot check that the daily total precip is correct
        self.assertEqual(rescaled.resample('1D').sum().iloc[0], self.snotel_mm['2023-01-01'])
        self.assertEqual(rescaled.resample('1D').sum().iloc[1], self.snotel_mm['2023-01-02'])

    def test_zero(self):
        '''
        Verify correct handling of zeros in the SNOTEL data, but NLDAS is showing precip.
        '''
        print("Need to implement this test")
    
    def test_missingday(self):
        '''
        Test handling of missing day in SNOTEL data.
        '''
        print("Need to implement this test")


#def test_partitionPrecip():

if __name__ == "__main__":
    unittest.main()