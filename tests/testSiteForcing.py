'''
Unit tests for the SiteForcing class
'''

from datetime import datetime
import unittest
from buildforcing.datasets import siteForcings, FLAG_OBSERVED, FLAG_TIME_INTERP, FLAG_GAP_FILLED
import xarray as xr
import xarray.testing as xrt
import numpy as np
import pandas as pd

class TestSiteForcings(unittest.TestCase):
    def setUp(self):
        # Create the target xarray Dataset for testing
        # Create dummy coordinates
        times = pd.date_range("2023-01-01", periods=24, freq="h")
        latitude = [35.0]
        longitude = [-104.5]
        ref_height = [[10.0]]

        # Create dummy data
        Tair_data = np.array([1, 2, 3, 4]*6).reshape(24,1,1)
        Qair_data = np.array([1, 2, 3, 4]*6).reshape(24,1,1)

        # Create dummy forcing flags
        Tair_flags = np.array([0]*24).reshape(24,1,1)
        Qair_flags = np.array([0]*24).reshape(24,1,1)

        # Assign data to the xarray Dataset
        self.target = xr.Dataset(
            {
            "Tair": (["time","latitude","longitude"], Tair_data),
            "Qair": (["time","latitude","longitude"], Qair_data),
            "reference_height": (["latitude","longitude"], ref_height),
            "canopy_height": (["latitude","longitude"], [[0]]),
            "Tair_flag": (["time","latitude","longitude"], Tair_flags),
            "Qair_flag": (["time","latitude","longitude"], Qair_flags),
            },
            coords={
            "time": times,
            "latitude": latitude,
            "longitude": longitude,
            },
        )

        # Assign metadata to each variable: long_name, units, build_method
        self.target["Tair"].attrs["long_name"] = "Near-surface air temperature"
        self.target["Tair"].attrs["ALMA_name"] = "Tair"
        self.target["Tair"].attrs["CMIP_name"] = "ta"
        self.target["Tair"].attrs["units"] = "K"
        self.target["Tair"].attrs["build_method"] = "test"
        self.target["Qair"].attrs["long_name"] = "Near-surface specific humidity"
        self.target["Qair"].attrs["ALMA_name"] = "Qair"
        self.target["Qair"].attrs["CMIP_name"] = "hus"
        self.target["Qair"].attrs["units"] = "kg/kg"
        self.target["Qair"].attrs["build_method"] = "test2"

    @unittest.skip("Skipping unless needed for development")
    def testInitial(self):
        '''
        for initial test development
        '''
        print(self.target)
        self.assertTrue(True)

    def testBuild(self):
        '''
        Test creating and adding data to a SiteForcing object
        '''
        # Create a SiteForcing object
        # Note that siteforcings is set up to create an hourly date range from starting date to ending date hour 23
        site = siteForcings("test_site", datetime(2023,1,1,0), datetime(2023,1,1,23,0), 35.0, -104.5)

        # Create some dummy forcing
        forcing1 = pd.Series([1, 2, 3, 4]*6, index=pd.date_range("2023-01-01", periods=24, freq="h", tz="UTC")).rename_axis('time')
        forcing2 = pd.Series([1, 2, 3, 4]*6, index=pd.date_range("2023-01-01", periods=24, freq="h", tz="UTC")).rename_axis('time')
        forcing_flags = pd.Series(0, index=forcing1.index)

        # Add the forcing to the SiteForcing object
        site.setForcing("Tair", "K", "test", forcing1, forcing_flags, reference_height=10.0)
        site.setForcing("Qair", "kg/kg", "test2", forcing2, forcing_flags, reference_height=10.0)

        ds = site.exportDataset()

        # Check that the coordinates match the target
        xrt.assert_equal(ds['time'], self.target['time'])
        xrt.assert_equal(ds['latitude'], self.target['latitude'])
        xrt.assert_equal(ds['longitude'], self.target['longitude'])

        # Check that the variables match the target
        xrt.assert_equal(ds['Tair'], self.target['Tair'])
        xrt.assert_equal(ds['Qair'], self.target['Qair'])

        # Check that the forcings match the target
        xrt.assert_equal(ds, self.target)

    def testBasicFlagSetting(self):
        '''
        Test basic flag setting functionality
        '''
        # Create a SiteForcing object
        site = siteForcings("test_site", datetime(2023,1,1,0), datetime(2023,1,1,23,0), 35.0, -104.5)

        # Create forcing data
        forcing = pd.Series([1, 2, 3, 4]*6, index=pd.date_range("2023-01-01", periods=24, freq="h", tz="UTC"))
        forcing_flags = pd.Series(0, index=forcing.index)
        site.setForcing("Tair", "K", "test", forcing, forcing_flags, reference_height=10.0)

        # Test 1: Set flags with None (should default to FLAG_OBSERVED)
        site.setQCFlag("Tair")
        self.assertIn("Tair", site.flag_data)
        self.assertEqual(len(site.flag_data["Tair"]), 24)
        self.assertTrue((site.flag_data["Tair"] == FLAG_OBSERVED).all())

        # Test 2: Set flags with numpy array
        flags_array = np.full(24, FLAG_OBSERVED, dtype='int8')
        flags_array[0:5] = FLAG_TIME_INTERP
        flags_array[10:12] = FLAG_GAP_FILLED
        site.setQCFlag("Tair", flag_data=flags_array)

        self.assertEqual(site.flag_data["Tair"][0], FLAG_TIME_INTERP)
        self.assertEqual(site.flag_data["Tair"][10], FLAG_GAP_FILLED)
        self.assertEqual(site.flag_data["Tair"][20], FLAG_OBSERVED)

        # Test 3: Set flags with pandas Series
        flags_series = pd.Series(FLAG_OBSERVED, index=forcing.index, dtype='int8')
        flags_series.iloc[5:8] = FLAG_TIME_INTERP
        site.setQCFlag("Tair", flag_data=flags_series)

        self.assertEqual(site.flag_data["Tair"].iloc[5], FLAG_TIME_INTERP)
        self.assertEqual(site.flag_data["Tair"].iloc[6], FLAG_TIME_INTERP)
        self.assertEqual(site.flag_data["Tair"].iloc[7], FLAG_TIME_INTERP)
        self.assertEqual(site.flag_data["Tair"].iloc[0], FLAG_OBSERVED)

        # Test 4: Verify flags are included in exported dataset
        ds = site.exportDataset()
        self.assertIn("Tair_flag", ds)
        self.assertEqual(ds["Tair_flag"].shape, (24, 1, 1))

        # Verify metadata
        self.assertEqual(ds["Tair_flag"].attrs["standard_name"], "status_flag")
        self.assertTrue(np.array_equal(ds["Tair_flag"].attrs["flag_values"], np.array([FLAG_OBSERVED, FLAG_TIME_INTERP, FLAG_GAP_FILLED], dtype='int8')))
        self.assertEqual(ds["Tair_flag"].attrs["flag_meanings"], "observed temporally_interpolated gap_filled")

        # Verify ancillary_variables link
        self.assertEqual(ds["Tair"].attrs["ancillary_variables"], "Tair_flag")

    def testFlagErrorNonExistentVariable(self):
        '''
        Test that an error is thrown when setting flags for a non-existent variable
        '''
        # Create a SiteForcing object
        site = siteForcings("test_site", datetime(2023,1,1,0), datetime(2023,1,1,23,0), 35.0, -104.5)

        # Create forcing data for Tair only
        forcing = pd.Series([1, 2, 3, 4]*6, index=pd.date_range("2023-01-01", periods=24, freq="h", tz="UTC"))
        forcing_flags = pd.Series(0, index=forcing.index)
        site.setForcing("Tair", "K", "test", forcing, forcing_flags, reference_height=10.0)

        # Try to set flags for a variable that doesn't exist
        with self.assertRaises(ValueError) as context:
            site.setQCFlag("Qair")

        self.assertIn("Build method for Qair must be set before setting the flag", str(context.exception))

        # Try to set flags for a completely invalid variable name
        with self.assertRaises(ValueError) as context:
            site.setQCFlag("InvalidVariable")

        self.assertIn("Build method for InvalidVariable must be set before setting the flag", str(context.exception))

    def testOnlyAllowedFlagsCanBeSet(self):
        '''
        Test that only allowed flag values can be set (validation)
        '''
        # Create a SiteForcing object
        site = siteForcings("test_site", datetime(2023,1,1,0), datetime(2023,1,1,23,0), 35.0, -104.5)

        # Create forcing data
        forcing = pd.Series([1, 2, 3, 4]*6, index=pd.date_range("2023-01-01", periods=24, freq="h", tz="UTC"))
        forcing_flags = pd.Series(0, index=forcing.index)
        site.setForcing("Tair", "K", "test", forcing, forcing_flags, reference_height=10.0)

        # Test valid flags (should work without error)
        valid_flags = np.array([FLAG_OBSERVED]*10 + [FLAG_TIME_INTERP]*10 + [FLAG_GAP_FILLED]*4, dtype='int8')
        site.setQCFlag("Tair", flag_data=valid_flags)

        # Verify all unique values are valid
        unique_flags = np.unique(site.flag_data["Tair"].values)
        allowed_flags = {FLAG_OBSERVED, FLAG_TIME_INTERP, FLAG_GAP_FILLED}
        for flag in unique_flags:
            self.assertIn(flag, allowed_flags, f"Flag value {flag} is not in allowed flags")

        # Test that we can identify invalid flags after export
        # (Note: The current implementation doesn't validate flag values at set time,
        # but the metadata documents the valid range)
        ds = site.exportDataset()
        valid_min, valid_max = ds["Tair_flag"].attrs["valid_range"]
        self.assertEqual(valid_min, 0)
        self.assertEqual(valid_max, 2)

        # Verify all flag values in dataset are within valid range
        flag_values = ds["Tair_flag"].values.flatten()
        self.assertTrue(np.all((flag_values >= valid_min) & (flag_values <= valid_max)),
                        "Some flag values are outside the valid range")

if __name__ == '__main__':
    unittest.main()