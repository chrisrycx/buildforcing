'''
Unit tests for the PNNLSnotel class
Must set an environment variable PNNL_DATA_PATH to the location of the PNNL data
'''

import unittest
from buildforcing.datasets import PNNLSnotel
import os

class TestPNNLSnotel(unittest.TestCase):
    def setUp(self):
        pass

    def testNonExistantSite(self):
        # Test an error is raised for a site that doesn't exist
        with self.assertRaises(ValueError):
            site = PNNLSnotel('nonexistant', storage_path=os.environ['SNOTEL_PATH'])

    def testNonPreciseLocation(self):
        # Test a site that does exist but doesn't have a precise location
        # Elk Cabin:
        # Elev 8210ft
        # Lat/Long 35.7,-105.81
        site = PNNLSnotel('Elk Cabin', storage_path=os.environ['SNOTEL_PATH'])
        self.assertAlmostEqual(site.elevation, 2503.0, places=1)
        self.assertAlmostEqual(site.latitude, 35.7, places=2)
        self.assertAlmostEqual(site.longitude, -105.81, places=2)
    
    def testPreciseLocation(self):
        # Test a site with a precise location
        # Tony Grove RS:
        site = PNNLSnotel('Tony Grove RS', storage_path=os.environ['SNOTEL_PATH'])
        self.assertAlmostEqual(site.elevation, 1927.68, places=2)
        self.assertAlmostEqual(site.latitude, 41.885683, places=3)
        self.assertAlmostEqual(site.longitude, -111.5692749, places=3)

if __name__ == '__main__':
    unittest.main()