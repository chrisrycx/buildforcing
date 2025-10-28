'''
Objects to get and store data from NLDAS or the PNNL snotel data (on Google Drive).
'''

from typing import TypedDict
import requests
from requests.auth import HTTPBasicAuth
import netrc # For handling .netrc files for authentication, standard library
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
from datetime import datetime, date, timedelta
from io import StringIO, TextIOWrapper
from timezonefinder import TimezoneFinder
import os
import xarray as xr
import numpy as np

# Flag values for data quality and interpolation status
FLAG_OBSERVED = 0              # Original measured/modeled data
FLAG_TIME_INTERP = 1           # Temporally interpolated
FLAG_GAP_FILLED = 2            # Gap-filled using other methods

class SnotelData(TypedDict):
    T_max_C: float
    T_min_C: float
    T_avg_C: float
    precip_mm: float
    swe_mm: float

class PNNLSnotel:
    '''
    Class to store and manipulate the PNNL Snotel data.
    Does not load data by default so that the metadata can be used without needing to load the data.
    '''
    
    def __init__(self, site_name: str, storage_path: str):
        self.site_name = site_name
        self.data: pd.DataFrame = pd.DataFrame()
        self.latitude: float = 0.0
        self.longitude: float = 0.0
        self.elevation: float = 0.0

        # Load PNNL data path from environment variable
        self.SNOTEL_PATH = storage_path
        self.PNNL_DATA_PATH = os.path.join(storage_path, 'bcqc_data_v2')

        # Load the metadata and associated data
        self.file_name: str = '' #Initialize here, set during metadata load
        self.precise_location: bool = False
        self.load_metadata()
        self.check_location()
        self.timezone = self.get_timezone()
            
    def load_metadata(self):
        '''
        Load the metadata for the PNNL Snotel data.
        '''

        # Load the metadata file
        summary_file = os.path.join(self.PNNL_DATA_PATH, 'SNOTEL_summary.csv')

        # For each line in the metadata file, split the line by commas and search for site name in column 3
        site_match = False
        with open(summary_file) as f:
            for line in f:
                # Remove \n from the line
                line = line.strip()
                column_values = line.split(',')
                if column_values[3] == self.site_name:
                    site_match = True
                    self.elevation: float = int(column_values[4])/3.28  # Convert feet to meters
                    self.latitude: float = float(column_values[5])
                    self.longitude: float = float(column_values[6])
                    self.start_date: datetime = datetime.strptime(column_values[7], '%m/%d/%Y')
                    self.end_date: datetime = datetime.strptime(column_values[8], '%m/%d/%Y')
        
        if not site_match:
            raise ValueError(f"Site name {self.site_name} not found in the PNNL Snotel metadata file.")
        
        # Build the file name for the site. The file name uses the site latitude and longitude to 5 decimal places: "bcqc_latitude_longitude.txt"
        # Note! This needs to be done before data loading since the lat and long may be updated with more precise values
        self.file_name = f'bcqc_{self.latitude:.5f}_{self.longitude:.5f}.txt'
    
    def check_location(self):
        '''
        Check for more precise location in Detre data file
        '''
        # Load the Detre data file
        precise_locations = pd.read_csv(os.path.join(self.SNOTEL_PATH, 'SNOTEL_Detre.csv'))
        precise_locations.set_index('site_name', inplace=True)

        if self.site_name in precise_locations.index:
            # Some sites have precise latitude = 'NA', which becomes NaN, check for that
            if pd.notna(precise_locations.loc[self.site_name, 'latitude_precise']):
                self.latitude = precise_locations.loc[self.site_name, 'latitude_precise']
                self.longitude = precise_locations.loc[self.site_name, 'longitude_precise']
                self.elevation = precise_locations.loc[self.site_name, 'elevation_precise']
                self.precise_location = True

    def load_data(self):

        # Build the full path to the file
        rawfile = os.path.join(self.PNNL_DATA_PATH,'bcqc_data',self.file_name)

        # Read the txt file into a pandas dataframe. No header, separator is spaces
        snotel_data = pd.read_csv(rawfile, delimiter=r'\s+', header=None, names=['Year', 'Month', 'Day', 'Precipitation', 'Max Temp', 'Min Temp', 'Avg Temp', 'Snow Water Equivalent'])

        # convert Month, Day, Year to a datetime object and set as index
        snotel_data['Date'] = pd.to_datetime(snotel_data[['Year', 'Month', 'Day']])
        snotel_data.set_index('Date', inplace=True)
        snotel_data.drop(columns=['Year', 'Month', 'Day'], inplace=True)

        # Rename columns
        snotel_data.rename(columns={'Precipitation': 'precip_in', 'Max Temp': 'T_max_F', 'Min Temp': 'T_min_F', 'Avg Temp': 'T_avg_F', 'Snow Water Equivalent': 'swe_in'}, inplace=True)

        # Convert temperatures to C
        snotel_data['T_max_C'] = (snotel_data['T_max_F'] - 32) * 5/9
        snotel_data['T_min_C'] = (snotel_data['T_min_F'] - 32) * 5/9
        snotel_data['T_avg_C'] = (snotel_data['T_avg_F'] - 32) * 5/9

        # Convert precipitation and swe to mm
        snotel_data['precip_mm'] = snotel_data['precip_in'] * 25.4
        snotel_data['swe_mm'] = snotel_data['swe_in'] * 25.4

        self.data = snotel_data[['T_max_C', 'T_min_C', 'T_avg_C', 'precip_mm', 'swe_mm']].copy()

        # Localize the index to the timezone of the site
        self.data.index = self.data.index.tz_localize(self.timezone)

    def get_timezone(self):
        '''
        Get the timezone for the site.
        '''
        # Use the timezonefinder package to get the timezone for the site
        tf = TimezoneFinder()
        return tf.timezone_at(lng=self.longitude, lat=self.latitude)
    
    def find_usable_dates(self) -> tuple[date, date]:
        '''
        Determine what date range is usable for the snotel data.
        
        Returns: Dates (associated with local timezone) of the first and last day with usable data.
        '''
        if self.data.empty:
            raise ValueError(f"No data loaded for site {self.site_name}. Please load the data first.")

        # Find the first date in the index where the 'T_max_C', 'T_min_C', and 'precip_mm' columns are not NaN
        good_index: pd.DatetimeIndex = self.data.index[self.data['T_max_C'].notna() & self.data['T_min_C'].notna() & self.data['precip_mm'].notna()]
        
        # There should probably be at least 15 days of data to be minimally usable for testing
        if len(good_index) < 15:
            raise ValueError(f'Not enough usable data for site {self.site_name}. Only {len(good_index)} days of data found.')

        return (good_index[0].to_pydatetime().date(), good_index[-1].to_pydatetime().date())

class siteNLDAS():
    '''
    Class to store and manipulate the NLDAS data for a given site.
    '''
    nldas_forcings = ['LWdown', 'PSurf','Qair','Rainf','SWdown','Tair','Wind_E','Wind_N']
    forcing_units = ['W/m^2','Pa','kg/kg','kg/m2','W/m^2','K','m/s','m/s']
    forcing_heights_m = [None,2,None,None,2,10,10]

    # Data URLs
    signin_url = "https://api.giovanni.earthdata.nasa.gov/signin"
    time_series_url = "https://api.giovanni.earthdata.nasa.gov/timeseries"

    def __init__(self, snotel: str, start_date: datetime, end_date: datetime, storage_path: str):
        '''
        Initialize the siteNLDAS class.
        Start and end dates should include hours.
        Snotel name can be either full name or "filename" (no spaces, no #, all lowercase).
        '''
        self.snotel_name = snotel
        self.snotel_filename = snotel.replace(" ","").replace("#","").lower()

        self.storage_path = storage_path
        self.latitude = None
        self.longitude = None
        self.start_date = start_date
        self.end_date = end_date
        self.data = pd.DataFrame()
        self.elevation = None

        # Initialize a session with retry logic
        self.session = requests.Session()
        retries = Retry(
            total=3,  # Number of retries
            backoff_factor=10,  # Wait time between retries
            status_forcelist=[404, 503],  # Retry on these HTTP status codes
            allowed_methods=["GET"]  # Retry only for GET requests
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def getNLDASElevation(self):
        '''
        Get the elevation for the site from the NLDAS topography data.
        '''
        nldas_topography = xr.open_dataset(os.path.join(self.storage_path, 'NLDAS_elevation.nc4'))
        self.elevation = nldas_topography.sel(lat=self.latitude, lon=self.longitude, method='nearest').NLDAS_elev.values.item()
        nldas_topography.close()
    
    def getAPIToken(self, refresh=False) -> str:
        '''
        Get an API token from the Earthdata Login system using .netrc file for authentication.
        Uses file locking to safely handle concurrent access from multiple processes.
        '''
        from filelock import FileLock
        
        # First check for existing saved token in home directory
        token_file = os.path.join(self.storage_path, ".earthdata_token")
        lock_file = f"{token_file}.lock"
        
        # Try reading without locking first (efficient for most cases)
        if os.path.exists(token_file) and not refresh:
            try:
                with open(token_file, "r") as f:
                    content = f.read().strip()
                    if content:  # Make sure file is not empty
                        dtstring, token = content.split(' ')
                        token_datetime = datetime.strptime(dtstring, "%Y-%m-%dT%H:%M:%S")
                        # Check if token is still valid (less than 24 hours old)
                        if datetime.now() - token_datetime < timedelta(hours=24):
                            return token
            except Exception as e:
                # Continue if there was any error reading the file
                print(f"Warning: Error reading token file: {e}. Will request a new token.")
                
        # Need to get a new token or refresh existing one
        with FileLock(lock_file, timeout=30):  # 30 seconds timeout to avoid deadlocks
            # Check again (another process might have updated the token)
            if os.path.exists(token_file) and not refresh:
                try:
                    with open(token_file, "r") as f:
                        content = f.read().strip()
                        if content:
                            dtstring, token = content.split(' ')
                            token_datetime = datetime.strptime(dtstring, "%Y-%m-%dT%H:%M:%S")
                            # Check if token is still valid (less than 24 hours old)
                            if datetime.now() - token_datetime < timedelta(hours=24):
                                return token
                except Exception:
                    # Continue with getting a new token
                    pass

            # Read .netrc file for credentials
            try:
                netrc_info = netrc.netrc()
            except FileNotFoundError:
                raise FileNotFoundError("No .netrc file found. Please create one with your Earthdata Login credentials.")
            except Exception as e:
                raise ValueError(f"Error reading .netrc file: {e}")

            username, _, password = netrc_info.authenticators("urs.earthdata.nasa.gov")

            # Make the GET request to get the token
            response = self.session.get(self.signin_url, auth=HTTPBasicAuth(username, password),
                         allow_redirects=True)

            # Check if the request was successful
            if response.status_code != 200:
                raise ValueError(f"Failed to get API token. Status code: {response.status_code}")

            # Extract the token from the response
            token = response.text.replace('"','')
            if not token:
                raise ValueError("No access token found in the response.")
            
            # Write to a temporary file first, then move it to ensure atomic write
            temp_token_file = f"{token_file}.tmp"
            with open(temp_token_file, "w") as f:
                f.write(f"{datetime.now().strftime('%Y-%m-%dT%H:%M:%S')} {token}")
                f.flush()
                os.fsync(f.fileno())  # Ensure data is written to disk
            
            # Atomically replace the old file with the new one
            os.replace(temp_token_file, token_file)

            return token
    
    def getforcingV0(self, forcing_name, request_start_date: datetime, request_end_date: datetime) -> pd.Series:
        '''
        Get data based on the forcing name. This uses the older API endpoint.
        I am inputing the start and end date here because I will need to split
        the request into multiple requests if the date range is too large.

        Note: There is a banner now on the returned data saying this API will no longer be available after 2025-10-31.
        '''
        print('Warning: Using deprecated NLDAS API v0, which will be discontinued after 2025-10-31. Please switch to API v1.')
        api_endpoint = 'https://hydro1.gesdisc.eosdis.nasa.gov/daac-bin/access/timeseries.cgi'

        if forcing_name not in self.nldas_forcings:
            raise ValueError(f"Invalid forcing name. Allowed values are: {self.nldas_forcings}")
        
        # Ensure date range is < 21 years
        # Actual range is 22 years, checking for 21 years to be safe and not to clash with getdata method which uses pd.DateOffset
        if (request_end_date - request_start_date).days > 365 * 21:
            raise ValueError(f"Date range is too large. Maximum is 20 years. Requested: {request_start_date} to {request_end_date}")

        print(f"Downloading {forcing_name} data from {request_start_date: %Y-%m-%d %H:00} to {request_end_date: %Y-%m-%d %H:00}")

        # Download the data
        params = {
            'variable': f'NLDAS2:NLDAS_FORA0125_H_v2.0:{forcing_name}',
            'startDate': request_start_date.strftime('%Y-%m-%dT%H'),
            'endDate': request_end_date.strftime('%Y-%m-%dT%H'),
            'location': f'GEOM:POINT({self.longitude:.2f}, {self.latitude:.2f})',
            'type': 'asc2'
        }

        # Make the GET request to the API
        # request_url = requests.Request('GET', self.base_url, params=params).prepare().url
        # print(f"Requesting data from URL: {request_url}")
        response = self.session.get(api_endpoint, params=params, timeout=60)

        # Check if the request was successful
        if response.status_code != 200:
            raise ValueError(f"Failed to download data. Status code: {response.status_code}")
            
        # Convert the response to a pandas dataframe
        nldas_csv = StringIO(response.text)
        # Find row in header starting with 'Date&Time' to determine how many rows to skip
        nldas_csv.seek(0)
        for i, line in enumerate(nldas_csv):
            if line.startswith('Date&Time'):
                skip_rows = i
                break

        nldas_csv.seek(0)  # Reset the StringIO object to the beginning
        nldas_data = pd.read_csv(nldas_csv, delimiter=r'\s+', skiprows=skip_rows, index_col=0, header=0)
        nldas_data.index = pd.to_datetime(nldas_data.index, format='%Y-%m-%dT%H:%M:%S', utc=True)

        # Return the data as a pandas series
        nldas_data = nldas_data['Data'].copy()
        nldas_data.name = forcing_name

        # Check if the data is empty
        if nldas_data.empty:
            raise ValueError(f"No data downloaded for {forcing_name} in the specified date range.")

        return nldas_data
    
    def getforcingV1(self, forcing_name, request_start_date: datetime, request_end_date: datetime) -> pd.Series:
        '''
        Get data based on the forcing name.
        I am inputing the start and end date here because I will need to split
        the request into multiple requests if the date range is too large.
        '''
        if forcing_name not in self.nldas_forcings:
            raise ValueError(f"Invalid forcing name. Allowed values are: {self.nldas_forcings}")
        
        # Ensure date range is < 21 years
        # Actual range is 22 years, checking for 21 years to be safe and not to clash with getdata method which uses pd.DateOffset
        if (request_end_date - request_start_date).days > 365 * 21:
            raise ValueError(f"Date range is too large. Maximum is 20 years. Requested: {request_start_date} to {request_end_date}")

        print(f"Downloading {forcing_name} data from {request_start_date: %Y-%m-%d %H:00} to {request_end_date: %Y-%m-%d %H:00}")

        # Download the data
        params = {
            'data': f'NLDAS_FORA0125_H_2_0_{forcing_name}',
            'location': f'[{self.latitude:.2f},{self.longitude:.2f}]',
            'time': f"{request_start_date.strftime('%Y-%m-%dT%H:00:00')}/{request_end_date.strftime('%Y-%m-%dT%H:00:00')}",
            'version': '2.0'
        }

        # Make the GET request to the API
        # request_url = requests.Request('GET', self.base_url, params=params).prepare().url
        # print(f"Requesting data from URL: {request_url}")
        response = self.session.get(self.time_series_url, params=params, timeout=60)

        # Check if the request was successful
        if response.status_code != 200:
            # Save response for troubleshooting
            self.response_error = response
            raise ValueError(f"Failed to download data. Status code: {response.status_code}")
            
        # Convert the response to a pandas dataframe
        nldas_csv = StringIO(response.text)
        skip_rows = 15 #header rows

        nldas_csv.seek(0)  # Reset the StringIO object to the beginning
        nldas_data = pd.read_csv(nldas_csv, skiprows=skip_rows, index_col=0)
        nldas_data.index = pd.to_datetime(nldas_data.index, format='%Y-%m-%d %H:%M', utc=True)

        # Return the data as a pandas series
        nldas_data = nldas_data['Data'].copy()
        nldas_data.name = forcing_name

        # Check if the data is empty
        if nldas_data.empty:
            raise ValueError(f"No data downloaded for {forcing_name} in the specified date range.")

        return nldas_data

    def getdata(self, latitude: float, longitude: float, use_api_v0: bool = False):
        '''
        Get the data for all forcings. This will also split the request into multiple requests if the date range is too large.
        '''
        self.latitude = latitude
        self.longitude = longitude

        if not use_api_v0:
            # Authorize and get the API token
            token = self.getAPIToken()
            self.session.headers.update({'authorizationtoken': token})  

        # Set chunk size for downloads
        chunk_size = 20 # years

        for forcing_name in self.nldas_forcings:
            forcing_series = pd.Series(dtype=float)
            next_start_date = self.start_date
            while next_start_date < self.end_date:
                # Get the end date for the next request
                next_end_date = min(next_start_date + pd.DateOffset(years=chunk_size), self.end_date)

                # Get the data for the forcing
                if use_api_v0:
                    new_forcing_series = self.getforcingV0(forcing_name, next_start_date, next_end_date)
                else:
                    new_forcing_series = self.getforcingV1(forcing_name, next_start_date, next_end_date)

                # Append the data to the existing data
                if forcing_series.empty:
                    forcing_series = new_forcing_series
                else:
                    forcing_series = pd.concat([forcing_series, new_forcing_series])

                # Update the start date for the next request
                next_start_date = next_start_date + pd.DateOffset(years=chunk_size, hours=1)

            # Add the forcing data to the dataframe
            self.data[forcing_name] = forcing_series

        # Get nldas elevation data
        self.getNLDASElevation()

    def findNetCDF(self) -> str | None:
        '''
        Find the NLDAS data file in the storage path with dates that are equal to or greater than the start date and less than or equal to the end date.
        The file follows the naming convention: "NLDAS_{latitude}_{longitude}_{start_date}_{end_date}.nc"
        With dates: YYYYMMDD
        '''
        file_list = os.listdir(self.storage_path)

        # Check the start and end dates for each file
        for file_name in file_list:
            if file_name.startswith(f'NLDAS_{self.snotel_filename}_'):
                # Extract the start and end dates from the file name
                date_parts = file_name[:-3].split('_')[2:4]
                file_start_date = pd.to_datetime(date_parts[0], format='%Y%m%d')
                file_end_date = pd.to_datetime(date_parts[1], format='%Y%m%d')

                # Check if the file's date range overlaps with the desired date range
                if file_start_date <= self.start_date and file_end_date >= self.end_date:
                    return file_name
        
        # If no file is found, return None
        return None

    def loadNetCDF(self):
        '''
        Load the NLDAS data from a NetCDF file: <storage_path>/<file_name>
        File follows the naming convention: "NLDAS_{latitude}_{longitude}_{start_date}_{end_date}.nc"
        With dates: YYYYMMDD
        Latitude and longitude to 2 decimal places.
        '''
        file_name = self.findNetCDF()
        if file_name is None:
            raise ValueError(f"No NLDAS data file found for the specified name {self.snotel_filename} and date range in {self.storage_path}")

        file_path = os.path.join(self.storage_path, file_name)

        # Open the dataset, this will fail if the file doesn't exist
        ds = xr.open_dataset(file_path)

        # Convert the xarray dataset to a pandas dataframe
        self.data = ds.to_dataframe()
        self.data = self.data.loc[self.start_date:self.end_date]  # Limit the data to the specified date range
        self.data.index = self.data.index.tz_localize('UTC')

        # Get the elevation from the dataset
        # Some files may not have elevation data, so load using method if error
        try:
            self.elevation = ds['elevation'].values.item()
        except KeyError:
            self.getNLDASElevation()
        
        ds.close()

    def saveNetCDF(self):
        '''
        Save the NLDAS data to a NetCDF file: <storage_path>/<file_name>
        File follows the naming convention: "NLDAS_{snotel_name}_{start_date}_{end_date}.nc"
        With dates: YYYYMMDD
        '''
        file_name = f'NLDAS_{self.snotel_filename}_{self.start_date.strftime("%Y%m%d")}_{self.end_date.strftime("%Y%m%d")}.nc'
        file_path = os.path.join(self.storage_path,file_name)

        # Remove problematic timezone information from the index
        data_notz = self.data.copy()
        data_notz.index = data_notz.index.tz_localize(None)
        ds = xr.Dataset.from_dataframe(data_notz)

        # Save elevation data
        ds['elevation'] = xr.DataArray(self.elevation, dims=[], attrs={'long_name': 'NLDAS Elevation', 'units': 'm'})  

        ds.to_netcdf(file_path, mode='w', format='NETCDF4', engine='netcdf4')

        ds.close()

class ForcingMetadata:
    '''
    Class to store metadata for a forcing variable.
    '''
    def __init__(self, 
                 ALMA_name: str,
                CMIP_name: str,
                long_name: str,
                units: str, 
        ):
        self.ALMA_name = ALMA_name
        self.CMIP_name = CMIP_name
        self.long_name = long_name
        self.units = units

class siteForcings:
    '''
    A class to store the forcings for a given site. Also contains metadata about how the forcings were created.
    '''
    allowed_forcings_metadata = {
        'LWdown': ForcingMetadata(ALMA_name='LWdown', CMIP_name='rlds', long_name='Surface downward longwave radiation', units='W/m2'),
        'SWdown': ForcingMetadata(ALMA_name='SWdown', CMIP_name='rsds', long_name='Surface downward shortwave radiation', units='W/m2'),
        'Psurf': ForcingMetadata(ALMA_name='Psurf', CMIP_name='ps', long_name='Surface Pressure', units='Pa'), #Note diff from NLDAS
        'Qair': ForcingMetadata(ALMA_name='Qair', CMIP_name='hus', long_name='Near-surface specific humidity', units='kg/kg'),
        'Rainf': ForcingMetadata(ALMA_name='Rainf', CMIP_name='prra', long_name='Rainfall rate', units='kg/m2/s'),
        'Snowf': ForcingMetadata(ALMA_name='Snowf', CMIP_name='prsn', long_name='Snowfall rate', units='kg/m2/s'),
        'Tair': ForcingMetadata(ALMA_name='Tair', CMIP_name='ta', long_name='Near-surface air Temperature', units='K'),
        'Wind': ForcingMetadata(ALMA_name='Wind', CMIP_name='ws', long_name='Near-surface wind speed', units='m/s')
    }

    def __init__(self, 
                 site_name, 
                 start_date: datetime, 
                 end_date: datetime, 
                 latitude: float, 
                 longitude: float,
                 reference_height: float = 10.0
                ):
        self.site_name = site_name
        self.start_date = start_date
        self.end_date = end_date

        # Set end date to be last hour of the day to be consistent with NLDAS
        self.latitude = latitude
        self.longitude = longitude
        self.reference_height = reference_height
        self.canopy_height = 0.0

        # Initialize data and metadata
        dfindex = pd.date_range(self.start_date, self.end_date, freq='h',tz='UTC') # hourly index
        self.forcings = pd.DataFrame(index=dfindex)
        self.forcings.index.name = 'time'

        self.build_methods = {}
        self.flag_data = {}  # Dictionary to store flag DataFrames for each forcing variable

    def loadNetCDF(self, storage_path: str):
        '''
        Load the forcings from a NetCDF file.
        Will construct file name following some sort of convention...
        '''
        pass

    def exportDataset(self) -> xr.Dataset:
        '''
        Export the data to an xarray Dataset
        '''
        # Create an xarray Dataset from the pandas dataframe, removing the timezone information
        forcings_notz = self.forcings.copy()
        forcings_notz.index = forcings_notz.index.tz_localize(None)
        output_ds = xr.Dataset.from_dataframe(forcings_notz)

        # Initial dataset only has time as a coordinate, add latitude and longitude as coordinates
        output_ds = output_ds.expand_dims({'latitude': [self.latitude], 'longitude': [self.longitude]},axis=[1,2])

        # Add reference height and canopy height variables 
        output_ds['reference_height'] = xr.DataArray(self.reference_height, dims=['latitude', 'longitude'], coords={'latitude': [self.latitude], 'longitude': [self.longitude]})
        output_ds['canopy_height'] = xr.DataArray(self.canopy_height, dims=['latitude', 'longitude'], coords={'latitude': [self.latitude], 'longitude': [self.longitude]})

        # Add metadata to each variable
        for forcing_name in self.forcings.columns:
            output_ds[forcing_name].attrs['build_method'] = self.build_methods[forcing_name]
            output_ds[forcing_name].attrs['ALMA_name'] = self.allowed_forcings_metadata[forcing_name].ALMA_name
            output_ds[forcing_name].attrs['CMIP_name'] = self.allowed_forcings_metadata[forcing_name].CMIP_name
            output_ds[forcing_name].attrs['long_name'] = self.allowed_forcings_metadata[forcing_name].long_name
            output_ds[forcing_name].attrs['units'] = self.allowed_forcings_metadata[forcing_name].units

        # Add flag variables for each forcing that has flag data
        for forcing_name, flag_series in self.flag_data.items():
            # Remove timezone from flag data index
            flag_series_notz = flag_series.copy()
            flag_series_notz.index = flag_series_notz.index.tz_localize(None)

            # Convert to xarray DataArray and expand dimensions to match forcing data
            flag_var_name = f'{forcing_name}_flag'
            flag_da = xr.DataArray.from_series(flag_series_notz)
            flag_da = flag_da.rename({'index': 'time'})
            flag_da = flag_da.expand_dims({'latitude': [self.latitude], 'longitude': [self.longitude]}, axis=[1, 2])

            # Add to dataset
            output_ds[flag_var_name] = flag_da

            # Add CF-compliant metadata
            output_ds[flag_var_name].attrs['long_name'] = f'Quality flag for {self.allowed_forcings_metadata[forcing_name].long_name}'
            output_ds[flag_var_name].attrs['standard_name'] = 'status_flag'
            output_ds[flag_var_name].attrs['flag_values'] = np.array([FLAG_OBSERVED, FLAG_TIME_INTERP, FLAG_GAP_FILLED], dtype='int8')
            output_ds[flag_var_name].attrs['flag_meanings'] = 'observed temporally_interpolated gap_filled'
            output_ds[flag_var_name].attrs['valid_range'] = np.array([0, 2], dtype='int8')
            output_ds[flag_var_name].attrs['comment'] = 'Flag indicates data quality and interpolation methods applied'

            # Link flag variable to data variable using ancillary_variables attribute
            if 'ancillary_variables' in output_ds[forcing_name].attrs:
                output_ds[forcing_name].attrs['ancillary_variables'] += f' {flag_var_name}'
            else:
                output_ds[forcing_name].attrs['ancillary_variables'] = flag_var_name

        return output_ds

    def setForcing(self, 
                   forcing_name: str,
                   forcing_units: str, 
                   build_method:str, 
                   forcing_data: pd.Series,
                   forcing_flags: pd.Series, 
                   reference_height: float
                   ):
        '''
        Set the forcing data for a given forcing name.
        '''
        # Ensure data is in allowed forcings has the correct units
        if forcing_name not in self.allowed_forcings_metadata:
            raise ValueError(f"Invalid forcing name. Allowed values are: {self.allowed_forcings_metadata.keys()}")
        if forcing_units != self.allowed_forcings_metadata[forcing_name].units:
            raise ValueError(f"Invalid units for {forcing_name}. Expected {self.allowed_forcings_metadata[forcing_name].units}, got {forcing_units}")

        # Ensure consistency in the reference height
        if reference_height != self.reference_height:
            raise ValueError(f"Reference height {reference_height} does not match the site reference height {self.reference_height}")

        # Ensure input data has the correct index
        if not forcing_data.index.equals(self.forcings.index):
            raise ValueError("Forcing data must have the same index as the site forcings")
        
        # Ensure there are no missing values in the forcing data
        if forcing_data.isnull().any():
            raise ValueError(f"Missing values in {forcing_name} forcing data")
        
        self.build_methods[forcing_name] = build_method
        self.forcings[forcing_name] = forcing_data
        self.setQCFlag(forcing_name, forcing_flags)

    def setQCFlag(self, forcing_name, flag_data=None):
        '''
        Set the quality/interpolation flags for a given forcing name.

        Parameters
        ----------
        forcing_name : str
            Name of the forcing variable
        flag_data : pd.Series or pd.DataFrame or np.ndarray, optional
            Flag values for each timestep. Can be:
            - pd.Series with same index as self.forcings
            - pd.DataFrame (will use first column)
            - np.ndarray with same length as self.forcings
            - None to initialize all flags to FLAG_OBSERVED (0)

            If not provided, all flags default to FLAG_OBSERVED (0).
        '''
        # Ensure the forcing name is in the build methods
        if forcing_name not in self.build_methods:
            raise ValueError(f"Build method for {forcing_name} must be set before setting the flag")

        # Process and store flag data
        if flag_data is None:
            # Initialize all flags to FLAG_OBSERVED (0)
            flags = pd.Series(FLAG_OBSERVED, index=self.forcings.index, dtype='int8', name=f'{forcing_name}_flag')
        elif isinstance(flag_data, pd.Series):
            # Validate index matches
            if not flag_data.index.equals(self.forcings.index):
                raise ValueError(f"Flag data index must match forcing data index for {forcing_name}")
            flags = flag_data.astype('int8')
            flags.name = f'{forcing_name}_flag'
        elif isinstance(flag_data, pd.DataFrame):
            # Use first column if DataFrame provided
            if not flag_data.index.equals(self.forcings.index):
                raise ValueError(f"Flag data index must match forcing data index for {forcing_name}")
            flags = flag_data.iloc[:, 0].astype('int8')
            flags.name = f'{forcing_name}_flag'
        elif isinstance(flag_data, np.ndarray):
            # Create Series from array
            if len(flag_data) != len(self.forcings.index):
                raise ValueError(f"Flag data length ({len(flag_data)}) must match forcing data length ({len(self.forcings.index)})")
            flags = pd.Series(flag_data, index=self.forcings.index, dtype='int8', name=f'{forcing_name}_flag')
        else:
            raise TypeError(f"flag_data must be pd.Series, pd.DataFrame, np.ndarray, or None. Got {type(flag_data)}")

        # Store the flag data
        self.flag_data[forcing_name] = flags

    def saveNetCDF(self, storage_path: str):
        '''
        Save the forcings to a NetCDF file.
        This requires some special encodings to match the target format.
        '''
        ds = self.exportDataset()
        time_encoding = {'calendar':'gregorian', 'units': 'hours since 1900-01-01 00:00:00'} #This will default to a 'proleptic_gregorian' calendar
        
        # Save
        ds.to_netcdf(storage_path, encoding={'time': time_encoding}, format='NETCDF4', engine='netcdf4',unlimited_dims=['time'])

            
        
       