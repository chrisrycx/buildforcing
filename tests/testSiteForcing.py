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
        times = pd.date_range("2023-01-01", periods=5, freq="h")
        latitude = [35.0]
        longitude = [-104.5]
        ref_height = [[10.0]]

        # Create dummy data
        var1_data = np.array([1, 2, 3, 4, 5]).reshape(5,1,1)
        var2_data = np.array([1, 2, 3, 4, 5]).reshape(5,1,1)

        # Assign data to the xarray Dataset
        self.target = xr.Dataset(
            {
            "var1": (["time","latitude","longitude"], var1_data),
            "var2": (["time","latitude","longitude"], var2_data),
            "reference_height": (["latitude","longitude"], ref_height),
            },
            coords={
            "time": times,
            "latitude": latitude,
            "longitude": longitude,
            },
        )

        # Assign metadata to each variable: long_name, units, build_method, and qc_flags
        self.target["var1"].attrs["long_name"] = "Variable 1"
        self.target["var1"].attrs["units"] = "m"
        self.target["var1"].attrs["build_method"] = "test"
        self.target["var1"].attrs["qc_flags"] = "error1"
        self.target["var2"].attrs["long_name"] = "Variable 2"
        self.target["var2"].attrs["units"] = "W/m2"
        self.target["var2"].attrs["build_method"] = "test2"
        #self.target["var2"].attrs["qc_flags"] = "error2" Try with no errors on var2

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
        site = siteForcings("test_site", datetime(2023,1,1,0), datetime(2023,1,1,4), 35.0, -104.5)

        # Create some dummy forcing
        forcing1 = pd.Series([1, 2, 3, 4, 5], index=pd.date_range("2023-01-01", periods=5, freq="h"))
        forcing2 = pd.Series([1, 2, 3, 4, 5], index=pd.date_range("2023-01-01", periods=5, freq="h"))

        # Add the forcing to the SiteForcing object
        site.setForcing("var1", "test", forcing1)
        site.setForcing("var2", "test2", forcing2)
        site.setQCFlag("var1", "error1")
        #site.setQCFlag("var2", "error") Try with no errors on var2

        ds = site.exportDataset()

        # Check that the coordinates match the target
        xrt.assert_equal(ds['time'], self.target['time'])
        xrt.assert_equal(ds['latitude'], self.target['latitude'])
        xrt.assert_equal(ds['longitude'], self.target['longitude'])

        # Check that the variables match the target
        xrt.assert_equal(ds['var1'], self.target['var1'])
        xrt.assert_equal(ds['var2'], self.target['var2'])

        # Check that the forcings match the target
        xrt.assert_equal(ds, self.target)

if __name__ == '__main__':
    unittest.main()