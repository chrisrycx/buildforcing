'''
Manually test the buildsite.py script in the current directory.
'''
import os
from buildforcing.buildsite import SiteBuilder
from buildforcing.downscale import downscaleTairV1
from datetime import datetime

buildforcing_version = '0.4.0'  #Specify manually since project toml doesn't change

site_name = 'Tony Grove RS'
start_date = datetime(2015, 1, 1)
end_date = datetime(2015, 1, 3)

# Create site builder for the specified site
forcing_builder = SiteBuilder(site_name)

# Test setting correction to something other than raw_nldas
forcing_builder.Tair_correction = downscaleTairV1

# Check if date range is valid
valid_start_date, valid_end_date = forcing_builder.findUsableDates()

# Print the valid date range
print(f'Valid date range for {site_name}: {valid_start_date} to {valid_end_date}')

# Calculate custom date range
if start_date < valid_start_date or end_date > valid_end_date:
    print(f'Custom date range {start_date} to {end_date} is not valid. Using valid date range instead.')
    start_date = valid_start_date
    end_date = valid_end_date

# Build the forcing data
forcings = forcing_builder.build(start_date, end_date)

forcing_storage_path = os.getenv('FORCING_PATH')
file_name = f'{site_name.replace(" ","").lower()}_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}_v{buildforcing_version}.nc'
forcings.saveNetCDF(os.path.join(forcing_storage_path,file_name))