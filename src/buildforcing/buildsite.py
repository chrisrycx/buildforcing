'''
The main entry point for the buildforcing package. This package is used to build the forcing data for the point model.
'''
from datetime import datetime
from buildforcing.datasets import PNNLSnotel, siteNLDAS, siteForcings
from buildforcing.downscale import downscaleTair
import os
import xarray as xr

# Load environmental variables
STORAGE_PATH = os.getenv('STORAGE_PATH')

def BuildSite(
        site_name: str,
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
    snotel = PNNLSnotel(site_name=site_name, storage_path=STORAGE_PATH)
    if not snotel.exists:
        raise ValueError(f'Site {site_name} does not exist in PNNL Snotel dataset.')

    # If start and end date not specified, use snotel start and end date
    if start_date is None:
        start_date = snotel.start_date
    if end_date is None:
        end_date = snotel.end_date

    # Load NLDAS data, locally if possible
    nldas = siteNLDAS(snotel.latitude, snotel.longitude, start_date, end_date)

    # Initial testing... reduce numbe of forcings to load
    nldas.nldas_forcings = ['Tair', 'Qair']

    try:
        nldas.loadNetCDF(STORAGE_PATH)
    except FileNotFoundError:
        nldas.getdata()
        nldas.saveNetCDF

    # Initialize the dataset
    model_forcings = siteForcings(site_name, start_date, end_date, snotel.latitude, snotel.longitude, 10)

    # Downscale the NLDAS data
    model_forcings.setForcing('Tair', 'downscaleTair', downscaleTair(nldas.Tair, snotel.Tmax, snotel.Tmin))
    model_forcings.setForcing('Qair', 'Raw Qair', nldas.Qair)

    return model_forcings.exportDataset()

if __name__ == '__main__':
    # testing
    site_name = 'Tony Grove RS'
    start_date = datetime(2015, 1, 1)
    end_date = datetime(2015, 1, 3)
    ds = BuildSite(site_name, start_date, end_date)
    print(ds)  # Print the dataset to verify the output