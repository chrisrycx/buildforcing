'''
Manually test the buildsite.py script in the current directory.
'''
import os
from buildforcing.buildsite import SiteBuilder
from buildforcing.downscale import downscaleTairV1
from datetime import datetime, date, time, timezone
from zoneinfo import ZoneInfo

buildforcing_version = 'test'  #Specify manually since project toml doesn't change

site_name = 'Virginia Lakes Ridge'
useValidDates = True  #If true the custom dates below are ignored
start_date = date(2020, 10, 1)
end_date = date(2021, 9, 30)

# Create site builder for the specified site
build_settings = '01011010'  
forcing_builder = SiteBuilder(site_name, settings_str=build_settings)

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

if useValidDates:
    start_date = valid_start_date
    end_date = valid_end_date

# The valid dates are specific to the SNOTEL data in the local timezone, so I will convert them to UTC
snotel_timezone = ZoneInfo(forcing_builder.snotel.get_timezone())
start_dt = datetime.combine(start_date, time(0,0), tzinfo=snotel_timezone)
end_dt = datetime.combine(end_date, time(23,0), tzinfo=snotel_timezone) # Ensure full day hourly coverage

# Convert to UTC and remove timezone info for consistency
start_dt = start_dt.astimezone(timezone.utc).replace(tzinfo=None)
end_dt = end_dt.astimezone(timezone.utc).replace(tzinfo=None)

# Ensure start date is no earlier than 1990-01-01, this matches what is used in production
min_start_dt = datetime(1990, 1, 1)
if start_dt < min_start_dt:
    start_dt = min_start_dt

# Build the forcing data
forcings = forcing_builder.build(start_dt, end_dt)

forcing_storage_path: str = os.getenv('FORCING_PATH') # type: ignore
file_name = f'{site_name.replace(" ","").lower()}_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}_s{build_settings}_v{buildforcing_version}.nc'
forcings.saveNetCDF(os.path.join(forcing_storage_path,site_name.replace(" ","").lower(),file_name))