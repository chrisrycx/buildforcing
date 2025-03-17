import unittest
import pandas as pd
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from buildforcing.downscale import downscaleTair

class TestDownscaleTair(unittest.TestCase):
    def setUp(self):
        # Create sample NLDAS temperature data (in Kelvin)
        self.nldas_Tair_K = pd.Series(
            [1 + 273.15, 2 + 273.15, 3 + 273.15, 1 + 273.15, 1 + 273.15, 0 + 273.15, 3 + 273.15, 3 + 273.15],
            index=pd.date_range("2023-01-01 07:00", periods=8, freq="6h", tz="UTC")
        )

        # Create sample SNOTEL max and min temperature data (in Celsius)
        self.snotel_Tmax_C = pd.Series(
            [4, 4],
            index=pd.date_range("2023-01-01", periods=2, freq="D", tz=ZoneInfo("America/Denver"))
        )
        self.snotel_Tmin_C = pd.Series(
            [0, 1],
            index=pd.date_range("2023-01-01", periods=2, freq="D", tz=ZoneInfo("America/Denver"))
        )

    def test_downscaleTair(self):
        # Call the function
        result = downscaleTair(self.nldas_Tair_K, self.snotel_Tmax_C, self.snotel_Tmin_C)

        # Assert the result is a pandas Series
        self.assertIsInstance(result, pd.Series)

        # Assert the result has the same index as the input NLDAS data
        self.assertTrue(result.index.equals(self.nldas_Tair_K.index))

        # Assert the result values are not NaN
        self.assertFalse(result.isna().any())

        # Expected result values
        expected_result = pd.Series(
            [0 + 273.15, 2 + 273.15, 4 + 273.15, 2 + 273.15, 2 + 273.15, 1 + 273.15, 4 + 273.15, 3 + 273.15],
            index=pd.date_range("2023-01-01 07:00", periods=8, freq="6H", tz="UTC")
        )

        # Assert each value within a tolerance
        for i in range(len(result)):
            self.assertAlmostEqual(result[i], expected_result[i], places=2)

if __name__ == "__main__":
    unittest.main()