'''
Unit tests for the SiteForcing class
'''

import unittest
from buildforcing.datasets import siteForcings
import xarray as xr
import numpy as np
import pandas as pd

class TestSiteForcings(unittest.TestCase):
    def setUp(self):
        # Create the target xarray Dataset for testing
        # Create dummy coordinates
        times = pd.date_range("2023-01-01", periods=5, freq="h")
        latitude = [35.0]
        longitude = [-104.5]
        ref_height = 2.0

        # Create dummy data
        var1_data = np.array([1, 2, 3, 4, 5])
        var2_data = np.array([1, 2, 3, 4, 5])

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
        self.target["var2"].attrs["qc_flags"] = "error2"

    def testInitial(self):
        '''
        for initial test development
        '''
        print(self.target)
        self.assertTrue(True)




if __name__ == '__main__':
    unittest.main()