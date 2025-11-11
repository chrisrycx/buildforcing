'''
The main entry point for the buildforcing package. This package is used to build the forcing data for the point model.
'''
from datetime import datetime, date
from buildforcing.datasets import PNNLSnotel, siteNLDAS, siteForcings
from buildforcing.downscale import getDownscaleFunction
import os
import xarray as xr
import pandas as pd
from typing import Callable


class SiteBuilder:
    '''
    Class for building forcing data for a site.
    '''
    settings_order = ['LWdown', 'Psurf', 'Qair', 'Rainf', 'PrecipPartition', 'SWdown', 'Tair', 'Wind']

    def __init__(self, site_name: str, settings_str: str = '00000000'):
        self.site_name = site_name
        self.start_date = None
        self.end_date = None
        self.snotel: PNNLSnotel
        self.nldas = None
        self.model_forcings = None

        # Parse settings string - It should be 8 characters long, each character representing the version of the downscaling method to use.
        # Settings are associated with variables in alphabetical order
        if len(settings_str) != 8:
            raise ValueError('Settings string must be 8 characters long.')
        self.settings = {
            'LWdown': int(settings_str[0]),
            'Psurf': int(settings_str[1]),
            'Qair': int(settings_str[2]),
            'Rainf': int(settings_str[3]),
            'PrecipPartition': int(settings_str[4]),
            'SWdown': int(settings_str[5]),
            'Tair': int(settings_str[6]),
            'Wind': int(settings_str[7])
        }

        # Define default functions for downscaling
        self.Tair_correction: Callable = getDownscaleFunction('Tair', self.settings['Tair'])
        self.Rainf_correction: Callable = getDownscaleFunction('Rainf', self.settings['Rainf'])
        self.precip_partition: Callable = getDownscaleFunction('precip_partition', self.settings['PrecipPartition']) # Partitioning is done to determine Snowf
        self.swrad_correction: Callable = getDownscaleFunction('SWdown', self.settings['SWdown'])
        self.lwrad_correction: Callable = getDownscaleFunction('LWdown', self.settings['LWdown'])
        self.Qair_correction: Callable = getDownscaleFunction('Qair', self.settings['Qair'])
        self.Psurf_correction: Callable = getDownscaleFunction('Psurf', self.settings['Psurf'])
        self.Wind_correction: Callable = getDownscaleFunction('Wind', self.settings['Wind'])

        # Load environment variables
        self.snotel_storage_path = os.getenv('SNOTEL_PATH')
        self.nldas_storage_path = os.getenv('NLDAS_PATH')

        if self.snotel_storage_path is None or self.nldas_storage_path is None:
            raise ValueError('Environment variables SNOTEL_PATH or NLDAS_PATH are not set.')

        # Load snotel data
        self.load_snotel_data(self.snotel_storage_path)

    def findUsableDates(self) -> tuple[date, date]:
        '''
        Determine what date range is usable for the forcing data based on the snotel data.
        Wrapper so this can be used in different contexts.
        '''
        return self.snotel.find_usable_dates()

    def load_snotel_data(self, storage_path: str):
        self.snotel = PNNLSnotel(site_name=self.site_name, storage_path=storage_path)
        self.snotel.load_data()

    def load_nldas_data(self, storage_path: str):
        # Load NLDAS data, locally if possible
        self.nldas = siteNLDAS(self.snotel.site_name, self.start_date, self.end_date, storage_path)
        self.nldas.loadNetCDF()
        
    def build(self, start_date: datetime, end_date: datetime):
        
        # Load nldas data
        self.start_date = start_date
        self.end_date = end_date
        self.load_nldas_data(self.nldas_storage_path)

        # Initialize forcings
        self.model_forcings = siteForcings(self.site_name, self.start_date, self.end_date, self.snotel.latitude, self.snotel.longitude, 10)

        # Corrections/Downscaling
        Tair = self.Tair_correction(self.nldas.data['Tair'], self.snotel.data['T_max_C'], self.snotel.data['T_min_C'])
        Qair = self.Qair_correction(self.nldas.data['Qair'], Tair['Tair'])
        Psurf = self.Psurf_correction(self.nldas.data['PSurf'], self.nldas.data['Tair'], snotel_elevation_m=self.snotel.elevation, nldas_elevation_m=self.nldas.elevation)
        swrad = self.swrad_correction(self.nldas.data['SWdown'])
        lwrad = self.lwrad_correction(self.nldas.data['LWdown'])
        precip_total = self.Rainf_correction(self.nldas.data['Rainf'], self.snotel.data['precip_mm'])
        precip = self.precip_partition(precip_total['Rainf'], Tair['Tair'], Qair['Qair'], Psurf['PSurf'])

        # Create a string describing precip processing
        precip_processing = f'Correction: {self.Rainf_correction.__name__} Partition: {self.precip_partition.__name__}'

        # Combine wind components
        nldas_wind = (self.nldas.data.Wind_N**2 + self.nldas.data.Wind_E**2)**0.5
        nldas_wind_flags = pd.Series(0, index=nldas_wind.index)

        # Set forcings
        self.model_forcings.setForcing('Tair', 'K', self.Tair_correction.__name__, Tair['Tair'],Tair['flags'], 10)
        self.model_forcings.setForcing('Qair', 'kg/kg', self.Qair_correction.__name__, Qair['Qair'], Qair['flags'], 10)
        self.model_forcings.setForcing('Psurf', 'Pa', self.Psurf_correction.__name__, Psurf['PSurf'], Psurf['flags'], 10)
        self.model_forcings.setForcing('Rainf', 'kg/m2/s', precip_processing, precip['rain_mm'] / 3600, precip['rain_flags'], 10)
        self.model_forcings.setForcing('Snowf', 'kg/m2/s', precip_processing, precip['snow_mm'] / 3600, precip['snow_flags'], 10)
        self.model_forcings.setForcing('SWdown', 'W/m2', self.swrad_correction.__name__, swrad['SWdown'], swrad['flags'], 10)
        self.model_forcings.setForcing('LWdown', 'W/m2', self.lwrad_correction.__name__, lwrad['LWdown'], lwrad['flags'], 10)
        self.model_forcings.setForcing('Wind', 'm/s', 'Raw Wind', nldas_wind, nldas_wind_flags, 10)

        return self.model_forcings