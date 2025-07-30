'''
Objects to get and store data from NLDAS or the PNNL snotel data (on Google Drive).
'''

from typing import TypedDict
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
from datetime import datetime, date
from io import StringIO, TextIOWrapper
from timezonefinder import TimezoneFinder
import os
import xarray as xr

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

        # Load PNNL data path from environment variable
        self.PNNL_DATA_PATH = os.path.join(storage_path, 'bcqc_data_v2')

        # Load the metadata and associated data
        self.load_metadata()
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
                    self.elevation: float = int(column_values[4])/3.28  # Convert meters to feet
                    self.latitude: float = float(column_values[5])
                    self.longitude: float = float(column_values[6])
                    self.start_date: datetime = datetime.strptime(column_values[7], '%m/%d/%Y')
                    self.end_date: datetime = datetime.strptime(column_values[8], '%m/%d/%Y')
        
        if not site_match:
            raise ValueError(f"Site name {self.site_name} not found in the PNNL Snotel metadata file.")
    
    def load_data(self):

        # Build the file name for the site. The file name uses the site latitude and longitude to 5 decimal places: "bcqc_latitude_longitude.txt"
        file_name = f'bcqc_{self.latitude:.5f}_{self.longitude:.5f}.txt'

        # Build the full path to the file
        rawfile = os.path.join(self.PNNL_DATA_PATH,'bcqc_data',file_name)

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

    # Data URL
    base_url = 'https://hydro1.gesdisc.eosdis.nasa.gov/daac-bin/access/timeseries.cgi'

    def __init__(self, latitude: float, longitude: float, start_date: datetime, end_date: datetime):
        self.latitude = latitude
        self.longitude = longitude
        self.start_date = start_date
        self.end_date = end_date
        self.data = pd.DataFrame()

        # Initialize a session with retry logic
        self.session = requests.Session()
        retries = Retry(
            total=2,  # Number of retries
            backoff_factor=1,  # Wait time between retries
            status_forcelist=[404],  # Retry on these HTTP status codes
            allowed_methods=["GET"]  # Retry only for GET requests
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def getforcing(self, forcing_name, request_start_date: datetime, request_end_date: datetime) -> pd.Series:
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
            'variable': f'NLDAS2:NLDAS_FORA0125_H_v2.0:{forcing_name}',
            'startDate': request_start_date.strftime('%Y-%m-%dT%H'),
            'endDate': request_end_date.strftime('%Y-%m-%dT%H'),
            'location': f'GEOM:POINT({self.longitude:.2f}, {self.latitude:.2f})',
            'type': 'asc2'
        }

        # Make the GET request to the API
        # request_url = requests.Request('GET', self.base_url, params=params).prepare().url
        # print(f"Requesting data from URL: {request_url}")
        response = self.session.get(self.base_url, params=params, timeout=60)

        # Check if the request was successful
        if response.status_code != 200:
            raise ValueError(f"Failed to download data. Status code: {response.status_code}")
            
        # Convert the response to a pandas dataframe
        nldas_csv = StringIO(response.text)
        skip_rows = 12 #header rows

        nldas_csv.seek(0)  # Reset the StringIO object to the beginning
        nldas_data = pd.read_csv(nldas_csv, delimiter=r'\s+', skiprows=skip_rows, index_col=0)
        nldas_data.index = pd.to_datetime(nldas_data.index, format='%Y-%m-%dT%H:%M:%S', utc=True)

        # Return the data as a pandas series
        nldas_data = nldas_data['Data'].copy()
        nldas_data.name = forcing_name

        # Check if the data is empty
        if nldas_data.empty:
            raise ValueError(f"No data downloaded for {forcing_name} in the specified date range.")

        return nldas_data

    def getdata(self):
        '''
        Get the data for all forcings. This will also split the request into multiple requests if the date range is too large.
        '''
        # Set chunk size for downloads
        chunk_size = 20 # years

        for forcing_name in self.nldas_forcings:
            forcing_series = pd.Series(dtype=float)
            next_start_date = self.start_date
            while next_start_date < self.end_date:
                # Get the end date for the next request
                next_end_date = min(next_start_date + pd.DateOffset(years=chunk_size), self.end_date)

                # Get the data for the forcing
                new_forcing_series = self.getforcing(forcing_name, next_start_date, next_end_date)

                # Append the data to the existing data
                if forcing_series.empty:
                    forcing_series = new_forcing_series
                else:
                    forcing_series = pd.concat([forcing_series, new_forcing_series])

                # Update the start date for the next request
                next_start_date = next_start_date + pd.DateOffset(years=chunk_size, hours=1)

            # Add the forcing data to the dataframe
            self.data[forcing_name] = forcing_series

    def findNetCDF(self, storage_path: str) -> str | None:
        '''
        Find the NLDAS data file in the storage path with dates that are equal to or greater than the start date and less than or equal to the end date.
        The file follows the naming convention: "NLDAS_{latitude}_{longitude}_{start_date}_{end_date}.nc"
        With dates: YYYYMMDD
        '''
        file_list = os.listdir(storage_path)

        # Check the start and end dates for each file
        for file_name in file_list:
            if file_name.startswith(f'NLDAS_{self.latitude:.2f}_{self.longitude:.2f}_'):
                # Extract the start and end dates from the file name
                date_parts = file_name[:-3].split('_')[3:5]
                file_start_date = pd.to_datetime(date_parts[0], format='%Y%m%d')
                file_end_date = pd.to_datetime(date_parts[1], format='%Y%m%d')

                # Check if the file's date range overlaps with the desired date range
                if file_start_date <= self.start_date and file_end_date >= self.end_date:
                    return file_name
        
        # If no file is found, return None
        return None

    def loadNetCDF(self, storage_path: str):
        '''
        Load the NLDAS data from a NetCDF file: <storage_path>/<file_name>
        File follows the naming convention: "NLDAS_{latitude}_{longitude}_{start_date}_{end_date}.nc"
        With dates: YYYYMMDD
        Latitude and longitude to 2 decimal places.
        '''
        file_name = self.findNetCDF(storage_path)
        if file_name is None:
            raise ValueError(f"No NLDAS data file found for the specified latitude, longitude, and date range in {storage_path}")
        
        file_path = os.path.join(storage_path, file_name)

        # Open the dataset, this will fail if the file doesn't exist
        ds = xr.open_dataset(file_path)

        # Convert the xarray dataset to a pandas dataframe
        self.data = ds.to_dataframe()
        self.data = self.data.loc[self.start_date:self.end_date]  # Limit the data to the specified date range
        self.data.index = self.data.index.tz_localize('UTC')

        ds.close()

    def saveNetCDF(self, storage_path: str):
        '''
        Save the NLDAS data to a NetCDF file: <storage_path>/<file_name>
        File follows the naming convention: "NLDAS_{latitude}_{longitude}_{start_date}_{end_date}.nc"
        With dates: YYYYMMDD
        Latitude and longitude to 2 decimal places.
        '''
        file_name = f'NLDAS_{self.latitude:.2f}_{self.longitude:.2f}_{self.start_date.strftime("%Y%m%d")}_{self.end_date.strftime("%Y%m%d")}.nc'
        file_path = os.path.join(storage_path,file_name)

        # Remove problematic timezone information from the index
        data_notz = self.data.copy()
        data_notz.index = data_notz.index.tz_localize(None)
        ds = xr.Dataset.from_dataframe(data_notz)
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
        self.qc_flags = {}

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

            if self.qc_flags.get(forcing_name) is not None:
                output_ds[forcing_name].attrs['qc_flags'] = self.qc_flags[forcing_name]

        return output_ds

    def setForcing(self, 
                   forcing_name: str,
                   forcing_units: str, 
                   build_method:str, 
                   forcing_data: pd.Series, 
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

    def setQCFlag(self, forcing_name, qc_flag):
        '''
        Set the QC flag for a given forcing name.
        '''
        # Ensure the forcing name is in the build methods
        if forcing_name not in self.build_methods:
            raise ValueError(f"Build method for {forcing_name} must be set before setting the QC flag")
        self.qc_flags[forcing_name] = qc_flag

    def saveNetCDF(self, storage_path: str):
        '''
        Save the forcings to a NetCDF file.
        This requires some special encodings to match the target format.
        '''
        ds = self.exportDataset()
        time_encoding = {'calendar':'gregorian', 'units': 'hours since 1900-01-01 00:00:00'} #This will default to a 'proleptic_gregorian' calendar
        
        # Save
        ds.to_netcdf(storage_path, encoding={'time': time_encoding}, format='NETCDF4', engine='netcdf4',unlimited_dims=['time'])

            
        
       