'''
The main entry point for the buildforcing package. This package is used to build the forcing data for the point model.
'''
from datetime import datetime
from buildforcing.datasets import PNNLSnotel, siteNLDAS, siteForcings
from buildforcing.downscale import downscaleTairV1, downscalePrecip, partitionPrecip
import os
import xarray as xr
import pandas as pd

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
    
    # Assess the date range of the snotel data
    usable_snotel_start_date, usable_snotel_end_date = findUsableDates(snotel)

    # Ensure date range does not exceed snotel data range
    # Use snotel start and end date if date range exceeds snotel data range
    if start_date is not None and end_date is not None:
        if start_date < usable_snotel_start_date:
            print(f'Start date {start_date} is before usable snotel start date {usable_snotel_start_date}. Updating start date.')
            start_date = usable_snotel_start_date
        if end_date > usable_snotel_end_date:
            print(f'End date {end_date} is after usable snotel end date {usable_snotel_end_date}. Updating end date.')
            end_date = usable_snotel_end_date

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
    Tair_corrected = downscaleTairV1(nldas.data.Tair, snotel.data.T_max_C, snotel.data.T_min_C)
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
