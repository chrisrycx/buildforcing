'''
Manually test the buildsite.py script in the current directory.
'''
import os
from buildforcing.buildsite import SiteBuilder
from buildforcing.downscale import downscaleTairV1
from datetime import datetime

buildforcing_version = '0.4.1'  #Specify manually since project toml doesn't change

site_name = 'Quemazon'
start_date = datetime(1980, 10, 1)
end_date = datetime(2025, 10, 1)

# Create site builder for the specified site
forcing_builder = SiteBuilder(site_name)

# Test setting correction to something other than raw_nldas
#forcing_builder.Tair_correction = downscaleTairV1

# Check if date range is valid
valid_start_date, valid_end_date = forcing_builder.findUsableDates()

# Print the valid date range
print(f'Valid date range for {site_name}: {valid_start_date} to {valid_end_date}')

# Calculate custom date range
if start_date < valid_start_date:
    print(f'Entered start date {start_date} is not valid. Using {valid_start_date} instead.')
    start_date = valid_start_date
if end_date > valid_end_date:
    print(f'Entered end date {end_date} is not valid. Using {valid_end_date} instead.')
    end_date = valid_end_date

# Build the forcing data
forcings = forcing_builder.build(start_date, end_date)

forcing_storage_path: str = os.getenv('FORCING_PATH') # type: ignore
file_name = f'{site_name.replace(" ","").lower()}_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}_s00000000_v{buildforcing_version}.nc'
forcings.saveNetCDF(os.path.join(forcing_storage_path,file_name))