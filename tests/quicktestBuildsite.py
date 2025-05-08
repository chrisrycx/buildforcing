'''
Manually test the buildsite.py script in the current directory.
'''
import os
from buildforcing.buildsite import BuildSite
from datetime import datetime

buildforcing_version = '0.3.0'  #Specify manually since project toml doesn't change

site_name = 'Lewis Peak'
start_date = datetime(2015, 1, 1)
end_date = datetime(2015, 3, 1, 23)
forcings = BuildSite(site_name, start_date, end_date)

forcing_storage_path = os.getenv('FORCING_PATH')
file_name = f'{site_name.replace(" ","").lower()}_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}_v{buildforcing_version}.nc'
forcings.saveNetCDF(os.path.join(forcing_storage_path,file_name))