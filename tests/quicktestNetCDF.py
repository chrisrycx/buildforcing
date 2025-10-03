'''
Manually test the NLDAS netCDF loading
'''
import os
from buildforcing.datasets import siteNLDAS, PNNLSnotel
from datetime import datetime

site_name = 'Tony Grove RS'
start_date = datetime(2015, 10, 1)
end_date = datetime(2016, 10, 1)

# Create the snotel dataset
snotel = PNNLSnotel(site_name, 'c:/Users/clmbn/NMT_PhD/data/snotel/')
print(f'Snotel site {snotel.site_name} found with coordinates: ({snotel.latitude}, {snotel.longitude})')

# Create the NLDAS dataset
nldas = siteNLDAS(snotel.site_name, snotel.latitude, snotel.longitude, start_date, end_date, os.getenv('NLDAS_PATH')) # type: ignore

# Check findNetCDF method
nldas_file = nldas.findNetCDF()
print(f'Found NLDAS file: {nldas_file}')

# Load the NLDAS data from the found file
nldas.loadNetCDF()

# Print out elevation data
print(f'SNOTEL Elevation: {snotel.elevation} m')
print(f'NLDAS Elevation: {nldas.elevation} m')