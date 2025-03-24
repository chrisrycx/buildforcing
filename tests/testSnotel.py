'''
Unit tests for the PNNLSnotel class
Must set an environment variable PNNL_DATA_PATH to the location of the PNNL data
'''

import unittest
from buildforcing.datasets import PNNLSnotel
import os

class TestPNNLSnotel(unittest.TestCase):
    def setUp(self):
        os.environ['PNNL_DATA_PATH'] = 'C:/Users/clmbn/NMT_PhD/bcqc_data_v2/'

    def testNonExistantSite(self):
        # Test a site that doesn't exist
        site = PNNLSnotel('nonexistant')
        self.assertFalse(site.exists)

    def testTonyGrove(self):
        # Test a site that does exist
        site = PNNLSnotel('Tony Grove RS')
        self.assertTrue(site.exists)
        self.assertAlmostEqual(site.elevation, 1930.5, places=1)
        self.assertAlmostEqual(site.latitude, 41.89, places=2)
        self.assertAlmostEqual(site.longitude, -111.57, places=2)
        self.assertEqual(site.start_date.year, 2009)
        self.assertEqual(site.end_date.year, 2018)

if __name__ == '__main__':
    unittest.main()