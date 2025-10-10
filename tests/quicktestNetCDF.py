'''
Manually test the NLDAS netCDF loading and data retrieval.
'''
import os
from buildforcing.datasets import siteNLDAS, PNNLSnotel
from datetime import datetime

site_name = 'Promontory'
start_date = datetime(2020, 1, 1)
end_date = datetime(2021, 10, 1)

# Create the snotel dataset
snotel = PNNLSnotel(site_name, os.getenv('SNOTEL_PATH')) # type: ignore
print(f'Snotel site {snotel.site_name} found with coordinates: ({snotel.latitude}, {snotel.longitude})')

# Create the NLDAS dataset
nldas = siteNLDAS(snotel.site_name, start_date, end_date, os.getenv('NLDAS_PATH')) # type: ignore

try:
    nldas.loadNetCDF()
    print(f"Existing NLDAS data found for {site_name}.")
    
except ValueError as e:
    print(f"No existing NLDAS data for {site_name}. Downloading...")

    # Download NLDAS data
    nldas.getdata(snotel.latitude, snotel.longitude)

    # Save the NLDAS data to the specified path
    print(f"Saving NLDAS data for {site_name}")
    nldas.saveNetCDF()

# Print out elevation data
print(f'SNOTEL Elevation: {snotel.elevation} m')
print(f'NLDAS Elevation: {nldas.elevation} m')