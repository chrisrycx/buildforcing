'''
Objects to get and store data from NLDAS or the PNNL snotel data (on Google Drive).
'''

import requests
import pandas as pd
from datetime import datetime, date
from io import StringIO, TextIOWrapper
from timezonefinder import TimezoneFinder
import os
import xarray as xr

class PNNLSnotel:
    '''
    Class to store and manipulate the PNNL Snotel data.
    '''
    
    def __init__(self, site_name: str, storage_path: str):
        self.site_name = site_name

        # Load PNNL data path from environment variable
        self.PNNL_DATA_PATH = os.path.join(storage_path, 'snotel')

        # Load the metadata and associated data
        self.exists = self.load_metadata()
        
        if self.exists:
            self.load_data()
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
                    self.end_date:datetime = datetime.strptime(column_values[8], '%m/%d/%Y')
        
        return site_match
    
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

        self.data: pd.DataFrame = snotel_data[['T_max_C', 'T_min_C', 'T_avg_C', 'precip_mm', 'swe_mm']].copy()

    def get_timezone(self):
        '''
        Get the timezone for the site.
        '''
        # Use the timezonefinder package to get the timezone for the site
        tf = TimezoneFinder()
        return tf.timezone_at(lng=self.longitude, lat=self.latitude)

class siteNLDAS():
    '''
    Class to store and manipulate the NLDAS data for a given site.
    '''
    nldas_forcings = ['LWdown','Qair','Rainf','SWdown','Tair','Wind_E','Wind_N']
    forcing_units = ['W/m^2','kg/kg','kg/m2','W/m^2','K','m/s','m/s']
    forcing_heights_m = [None,2,None,None,2,10,10]

    # Data URL
    base_url = 'https://hydro1.gesdisc.eosdis.nasa.gov/daac-bin/access/timeseries.cgi'

    def __init__(self, latitude: float, longitude: float, start_date: datetime, end_date: datetime):
        self.latitude = latitude
        self.longitude = longitude
        self.start_date = start_date
        self.end_date = end_date
        self.data = pd.DataFrame()

    def getforcing(self, forcing_name):
        '''
        Get data based on the forcing name.
        '''
        if forcing_name not in self.nldas_forcings:
            raise ValueError(f"Invalid forcing name. Allowed values are: {self.nldas_forcings}")

        print(f"Downloading {forcing_name} data from {self.start_date} to {self.end_date}")
                             
        # Download the data
        params = {
            'variable': f'NLDAS2:NLDAS_FORA0125_H_v2.0:{forcing_name}',
            'startDate': self.start_date.strftime('%Y-%m-%dT00'),
            'endDate': self.end_date.strftime('%Y-%m-%dT23'),
            'location': f'GEOM:POINT({self.longitude:.2f}, {self.latitude:.2f})',
            'type': 'asc2'
        }

        # Make the GET request to the API
        response = requests.get(self.base_url, params=params, timeout=60)

        # Check if the request was successful
        if response.status_code != 200:
            raise ValueError(f"Failed to download data. Status code: {response.status_code}")
            
        # Convert the response to a pandas dataframe
        nldas_csv = StringIO(response.text)
        skip_rows = 12 #header rows

        nldas_csv.seek(0)  # Reset the StringIO object to the beginning
        nldas_data = pd.read_csv(nldas_csv, delimiter=r'\s+', skiprows=skip_rows, index_col=0, parse_dates=True)

        # Load the data into a Pandas DataFrame, skipping the necessary rows
        nldas_data.columns = [forcing_name]
        self.data = self.data.join(nldas_data, how='outer')

    def getdata(self):
        '''
        Get the data for all forcings.
        '''
        for forcing_name in self.nldas_forcings:
            self.getforcing(forcing_name)

    def loadNetCDF(self, storage_path: str):
        '''
        Load the NLDAS data from a NetCDF file: <storage_path>/nldas/<file_name>
        File follows the naming convention: "NLDAS_{latitude}_{longitude}_{start_date}_{end_date}.nc"
        With dates: YYYYMMDD
        Latitude and longitude to 2 decimal places.
        '''
        file_name = f'NLDAS_{self.latitude:.2f}_{self.longitude:.2f}_{self.start_date.strftime("%Y%m%d")}_{self.end_date.strftime("%Y%m%d")}.nc'
        file_path = os.path.join(storage_path, file_name)

        # Open the dataset, this will fail if the file doesn't exist
        ds = xr.open_dataset(file_path)

        # Convert the xarray dataset to a pandas dataframe
        self.data = ds.to_dataframe()

    def saveNetCDF(self, storage_path: str):
        '''
        Save the NLDAS data to a NetCDF file: <storage_path>/nldas/<file_name>
        File follows the naming convention: "NLDAS_{latitude}_{longitude}_{start_date}_{end_date}.nc"
        With dates: YYYYMMDD
        Latitude and longitude to 2 decimal places.
        '''
        file_name = f'NLDAS_{self.latitude:.2f}_{self.longitude:.2f}_{self.start_date.strftime("%Y%m%d")}_{self.end_date.strftime("%Y%m%d")}.nc'
        file_path = os.path.join(storage_path, file_name)
        ds = xr.Dataset.from_dataframe(self.data)
        ds.to_netcdf(file_path, mode='w', format='NETCDF4', engine='netcdf4')

class siteForcings:
    '''
    A class to store the forcings for a given site. Also contains metadata about how the forcings were created.
    '''

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
        self.latitude = latitude
        self.longitude = longitude
        self.reference_height = reference_height

        # Initialize data and metadata
        dfindex = pd.date_range(start_date, end_date, freq='h') # hourly index
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
        # Create an xarray Dataset
        output_ds = xr.Dataset.from_dataframe(self.forcings)

        # Initial dataset only has time as a coordinate, add latitude and longitude as coordinates
        output_ds = output_ds.expand_dims({'latitude': [self.latitude], 'longitude': [self.longitude]},axis=[1,2])

        # Add reference height variable 
        output_ds['reference_height'] = xr.DataArray(self.reference_height, dims=['latitude', 'longitude'], coords={'latitude': [self.latitude], 'longitude': [self.longitude]})

        # Add metadata to each variable
        for forcing_name in self.forcings.columns:
            output_ds[forcing_name].attrs['build_method'] = self.build_methods[forcing_name]

            if self.qc_flags.get(forcing_name) is not None:
                output_ds[forcing_name].attrs['qc_flags'] = self.qc_flags[forcing_name]

        return output_ds


    def setForcing(self, forcing_name: str, build_method:str, forcing_data: pd.Series, reference_height: float):
        '''
        Set the forcing data for a given forcing name.
        '''
        # Ensure consistency in the reference height
        if reference_height != self.reference_height:
            raise ValueError(f"Reference height {reference_height} does not match the site reference height {self.reference_height}")

        # Ensure input data has the correct index
        if not forcing_data.index.equals(self.forcings.index):
            raise ValueError("Forcing data must have the same index as the site forcings")
        
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

            
        
       