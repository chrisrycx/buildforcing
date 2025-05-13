'''
The main entry point for the buildforcing package. This package is used to build the forcing data for the point model.
'''
from datetime import datetime
from buildforcing.datasets import PNNLSnotel, siteNLDAS, siteForcings
from buildforcing.downscale import downscaleTairV1, downscalePrecip, partitionPrecip
import os
import xarray as xr
import pandas as pd
from typing import Callable

def raw_nldas(nldas_data):
    '''
    Just a paththru function
    '''
    return nldas_data

class SiteBuilder:
    '''
    Class for building forcing data for a site.
    '''
    # Define default functions for downscaling
    Tair_correction: Callable = raw_nldas
    precip_correction: Callable = raw_nldas
    precip_partition: Callable = partitionPrecip
    swrad_correction: Callable = raw_nldas
    lwrad_correction: Callable = raw_nldas
    Qair_correction: Callable = raw_nldas

    @classmethod
    def findUsableDates(snotel: PNNLSnotel) -> tuple[datetime, datetime]:
        '''
        Determine what date range is usable for the forcing data based on the snotel data.
        Depending on the downscaling method, this may change.
        '''

        # Find the first date in the index where the 'T_max_C', 'T_min_C', and 'precip_mm' columns are not NaN
        good_index: pd.DatetimeIndex = snotel.data.index[snotel.data['T_max_C'].notna() & snotel.data['T_min_C'].notna() & snotel.data['precip_mm'].notna()]
        
        # There should probably be at least 15 days of data to be minimally usable for testing
        if len(good_index) < 15:
            raise ValueError(f'Not enough usable data for site {snotel.site_name}. Only {len(good_index)} days of data found.')
        
        # Remove timezone information from the index
        good_index = good_index.tz_localize(None)
        #good_index = good_index.tz_convert('UTC').tz_localize(None)
        
        return (good_index[0].to_pydatetime(), good_index[-1].to_pydatetime())  # Return the first and last date in the index


    def __init__(self, site_name: str, start_date: datetime = None, end_date: datetime = None):
        self.site_name = site_name
        self.start_date = start_date
        self.end_date = end_date
        self.snotel = None
        self.nldas = None
        self.model_forcings = None

    def load_snotel_data(self, storage_path: str):
        self.snotel = PNNLSnotel(site_name=self.site_name, storage_path=storage_path)
        if not self.snotel.exists:
            raise ValueError(f'Site {self.site_name} does not exist in PNNL Snotel dataset.')

    def load_nldas_data(self, storage_path: str):
        self.nldas = siteNLDAS(self.snotel.latitude, self.snotel.longitude, self.start_date, self.end_date)
        try:
            self.nldas.loadNetCDF(storage_path)
        except FileNotFoundError:
            self.nldas.getdata()
            self.nldas.saveNetCDF(storage_path)

    def downscale_data(self):
        Tair_corrected = downscaleTairV1(self.nldas.data.Tair, self.snotel.data.T_max_C, self.snotel.data.T_min_C)
        precip_corrected = downscalePrecip(self.nldas.data.Rainf, self.snotel.data.precip_mm)
        precip_partitioned = partitionPrecip(precip_corrected, Tair_corrected)

        self.model_forcings.setForcing('Tair', 'K', 'downscaleTair', Tair_corrected, 10)
        self.model_forcings.setForcing('Rainf', 'kg/m2/s', 'partition v0', precip_partitioned['rain_mm'] / 3600, 10)
        self.model_forcings.setForcing('Snowf', 'kg/m2/s', 'partition v0', precip_partitioned['snow_mm'] / 3600, 10)

    def build(self):
        # Load environment variables
        snotel_storage_path = os.getenv('SNOTEL_PATH')
        nldas_storage_path = os.getenv('NLDAS_PATH')

        if snotel_storage_path is None or nldas_storage_path is None:
            raise ValueError('Environment variables SNOTEL_PATH or NLDAS_PATH are not set.')

        # Load data
        self.load_snotel_data(snotel_storage_path)
        self.load_nldas_data(nldas_storage_path)

        # Determine usable dates
        usable_start, usable_end = findUsableDates(self.snotel)
        self.start_date = max(self.start_date or usable_start, usable_start)
        self.end_date = min(self.end_date or usable_end, usable_end)

        # Initialize forcings
        self.model_forcings = siteForcings(self.site_name, self.start_date, self.end_date, self.snotel.latitude, self.snotel.longitude, 10)

        # Downscale and set forcings
        self.downscale_data()

        # Combine wind components
        nldas_wind = (self.nldas.data.Wind_N**2 + self.nldas.data.Wind_E**2)**0.5
        self.model_forcings.setForcing('Wind', 'm/s', 'Raw Wind', nldas_wind, 10)

        return self.model_forcings