'''
Unit tests for the SiteForcing class
'''

from datetime import datetime
import unittest
from buildforcing.datasets import siteForcings
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

        # Assign data to the xarray Dataset
        self.target = xr.Dataset(
            {
            "Tair": (["time","latitude","longitude"], Tair_data),
            "Qair": (["time","latitude","longitude"], Qair_data),
            "reference_height": (["latitude","longitude"], ref_height),
            "canopy_height": (["latitude","longitude"], [[0]]),
            },
            coords={
            "time": times,
            "latitude": latitude,
            "longitude": longitude,
            },
        )

        # Assign metadata to each variable: long_name, units, build_method, and qc_flags
        self.target["Tair"].attrs["long_name"] = "Near-surface air temperature"
        self.target["Tair"].attrs["ALMA_name"] = "Tair"
        self.target["Tair"].attrs["CMIP_name"] = "ta"
        self.target["Tair"].attrs["units"] = "K"
        self.target["Tair"].attrs["build_method"] = "test"
        self.target["Tair"].attrs["qc_flags"] = "error1"
        self.target["Qair"].attrs["long_name"] = "Near-surface specific humidity"
        self.target["Qair"].attrs["ALMA_name"] = "Qair"
        self.target["Qair"].attrs["CMIP_name"] = "hus"
        self.target["Qair"].attrs["units"] = "kg/kg"
        self.target["Qair"].attrs["build_method"] = "test2"
        #self.target["Qair"].attrs["qc_flags"] = "error2" Try with no errors on Qair

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
        forcing1 = pd.Series([1, 2, 3, 4]*6, index=pd.date_range("2023-01-01", periods=24, freq="h", tz="UTC"))
        forcing2 = pd.Series([1, 2, 3, 4]*6, index=pd.date_range("2023-01-01", periods=24, freq="h", tz="UTC"))

        # Add the forcing to the SiteForcing object
        site.setForcing("Tair", "K", "test", forcing1, reference_height=10.0)
        site.setForcing("Qair", "kg/kg", "test2", forcing2, reference_height=10.0)
        site.setQCFlag("Tair", "error1")
        #site.setQCFlag("Qair", "error") Try with no errors on Qair

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

if __name__ == '__main__':
    unittest.main()