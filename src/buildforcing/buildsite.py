'''
The main entry point for the buildforcing package. This package is used to build the forcing data for the point model.
'''
from datetime import datetime
from buildforcing.datasets import PNNLSnotel, siteNLDAS, siteForcings
from buildforcing.downscale import downscaleTair, downscalePrecip, partitionPrecip
import os
import xarray as xr

def BuildSite(
        site_name: str,
        start_date: datetime = None,
        end_date: datetime = None
        ) -> siteForcings:
    '''
    Build the forcing data for a site using NLDAS and PNNL Snotel data.

    Parameters
    ----------
    site_name : str
        The name of the site being built.
    start_date : datetime
        The start date of the forcing data.
    end_date : datetime
        The end date of the forcing data.
    forcings : list[str]
        The forcings to build for the site. Should match NLDAS variable names.

    Returns
    -------
    xarray dataset which matches LM4.1 netCDF format
    '''
    # Convert STORAGE_PATH to specified folder
    snotel_storage_path = os.getenv('SNOTEL_PATH')
    nldas_storage_path = os.getenv('NLDAS_PATH')

    # Exit if no environment variable is set
    if snotel_storage_path is None:
        raise ValueError('SNOTEL_PATH environment variable not set.')
    if nldas_storage_path is None:
        raise ValueError('NLDAS_PATH environment variable not set.')

    # Load snotel data, this will fail if site doesn't exist
    snotel = PNNLSnotel(site_name=site_name, storage_path=snotel_storage_path)
    if not snotel.exists:
        raise ValueError(f'Site {site_name} does not exist in PNNL Snotel dataset.')

    # If start and end date not specified, use snotel start and end date
    if start_date is None:
        start_date = snotel.start_date
    if end_date is None:
        end_date = snotel.end_date

    # Load NLDAS data, locally if possible
    # Forcings 'LWdown','Psurf','Qair','Rainf','SWdown','Tair','Wind_E','Wind_N'
    nldas = siteNLDAS(snotel.latitude, snotel.longitude, start_date, end_date)

    try:
        nldas.loadNetCDF(nldas_storage_path)
    except FileNotFoundError:
        nldas.getdata()
        nldas.saveNetCDF(nldas_storage_path)

    # Initialize the dataset
    model_forcings = siteForcings(site_name, start_date, end_date, snotel.latitude, snotel.longitude, 10)

    # -- Downscale the NLDAS data to create model forcings: 'LWdown','Psurf','Qair','Rainf','Snowf','SWdown','Tair','Wind'
    print('Warning: forcing conversion not yet implemented correctly for Qair and Wind.')
    model_forcings.setForcing('LWdown','W/m2', 'Raw LW down', nldas.data.LWdown, 10)
    model_forcings.setForcing('SWdown','W/m2','Raw SW down', nldas.data.SWdown, 10)
    model_forcings.setForcing('Psurf','Pa', 'Raw P surf', nldas.data.PSurf, 10)
    model_forcings.setForcing('Qair','kg/kg', 'Raw Qair', nldas.data.Qair, 10)
    
    # Downscale temperature and use for partition precipitation
    Tair_corrected = downscaleTair(nldas.data.Tair, snotel.data.T_max_C, snotel.data.T_min_C)
    precip_corrected = downscalePrecip(nldas.data.Rainf, snotel.data.precip_mm)
    precip_partitioned = partitionPrecip(precip_corrected, Tair_corrected)

    model_forcings.setForcing('Tair','K', 'downscaleTair', Tair_corrected, 10)
    model_forcings.setForcing('Rainf','kg/m2/s','partition v0', precip_partitioned['rain_mm']/3600, 10)  # Need rainfall rate kg/m2/s
    model_forcings.setForcing('Snowf','kg/m2/s','partition v0', precip_partitioned['snow_mm']/3600, 10)  # Need snowfall rate kg/m2/s
    
    # Combine wind components
    nldas_wind = nldas.data.Wind_N**2 + nldas.data.Wind_E**2
    nldas_wind = nldas_wind**0.5
    model_forcings.setForcing('Wind', 'm/s','Raw Wind', nldas_wind, 10)

    return model_forcings

if __name__ == '__main__':
    # testing
    site_name = 'Tony Grove RS'
    start_date = datetime(2015, 1, 1)
    end_date = datetime(2015, 2, 1, 23)
    forcings = BuildSite(site_name, start_date, end_date)
    forcings.saveNetCDF('C:/Users/clmbn/NMT_PhD/data/forcing/tonygrove_20150101_20150201_v0.nc')