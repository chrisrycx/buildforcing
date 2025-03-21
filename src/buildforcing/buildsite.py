'''
The main entry point for the buildforcing package. This package is used to build the forcing data for the point model.
'''
from datetime import datetime
from buildforcing.datasets import PNNLSnotel, siteNLDAS, siteForcings
import os
import xarray as xr

# Load environmental variables
STORAGE_PATH = os.getenv('STORAGE_PATH')

def BuildSite(
        site_name: str,
        forcings: list[str],
        start_date: datetime = None,
        end_date: datetime = None
        ) -> xr.Dataset:
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
    # Load snotel data, this will fail if site doesn't exist
    snotel = PNNLSnotel()

    # If start and end date not specified, use snotel start and end date
    if start_date is None:
        start_date = snotel.start_date
    if end_date is None:
        end_date = snotel.end_date

    # Load NLDAS data, locally if possible
    nldas = siteNLDAS(site_name, latitude, longitude, forcings, start_date, end_date)
    try:
        nldas.loadNetCDF(STORAGE_PATH)
    except FileNotFoundError:
        nldas.downloadForcings()
        nldas.saveNetCDF

    # Initialize the dataset
    site_forcing = Dataset(site_name, start_date, end_date)

    # Downscale the NLDAS data
    site.setForcing('Tair', 'downscaleTair', downscaleTair(nldas.Tair, snotel.Tmax, snotel.Tmin))
    site.setForcing('P', 'downscaleP', downscaleP(nldas.P, snotel.P))

    return site_forcing.exportDataset()