'''
A module for performing quality control on SNOTEL data.
- Flagging suspect data points
- Replacing bad data
- Filling gaps
'''
import pandas as pd
import numpy as np

def check_outliers(data: np.ndarray, sigma_threshold: float = 3.0) -> np.ndarray:
    '''
    Identify outliers in a dataset based on a specified number of standard deviations from mean.

    Parameters:
    data (np.ndarray): Input data array.
    sigma_threshold (float): Number of standard deviations to use as the threshold for identifying outliers.

    Returns:
    np.ndarray: Boolean array where True indicates an outlier.
    '''
    mean = np.mean(data)
    std_dev = np.std(data)
    upper_limit = mean + sigma_threshold * std_dev
    lower_limit = mean - sigma_threshold * std_dev
    return (data > upper_limit) | (data < lower_limit)

def qc_maxmin_temperatures(df: pd.DataFrame) -> pd.DataFrame:
    '''
    Quality control SNOTEL max/min temperature data.
    Expected input DataFrame columns: ['Tmax', 'Tmin'], daily data in local timezone.

    QC Checks:
    1. Flag outlier values as suspect based on data stats
    2. Flag inconsistent Tmax/Tmin pairs
    3. Flag outlier diurnal temperature ranges based on data stats

    Output DataFrame with columns ['Tmax_bad','Tmin_bad']
    '''
    # Copy input DataFrame to avoid modifying original
    df = df.copy()
    df.columns = ['Tmax', 'Tmin']

    # Check for amount of data, if less than 365 days, output a warning
    if len(df) < 365:
        print("Warning: Less than 365 days of data. QC may be unreliable.")

    # Initialize QC flag columns
    df['Tmax_outlier'] = False
    df['Tmin_outlier'] = False
    df['DTR_outlier'] = False
    df['Tmax_Tmin_inconsistent'] = False

    # Check for outliers in Tmax and Tmin
    df['Tmax_outlier'] = check_outliers(df['Tmax'].values)
    df['Tmin_outlier'] = check_outliers(df['Tmin'].values)
    # Check for inconsistent Tmax/Tmin pairs
    df['Tmax_Tmin_inconsistent'] = df['Tmax'] < df['Tmin']
    # Calculate Diurnal Temperature Range (DTR)
    df['DTR'] = df['Tmax'] - df['Tmin']
    # Check for outliers in DTR
    df['DTR_outlier'] = check_outliers(df['DTR'].values)

    # Interpret the flags
    df['Tmax_bad'] = False
    df['Tmin_bad'] = False
    df.loc[df['Tmax_Tmin_inconsistent'], ['Tmax_bad', 'Tmin_bad']] = True # Both bad if inconsistent
    df.loc[df['Tmax_outlier'] & df['Tmin_outlier'], ['Tmax_bad', 'Tmin_bad']] = True # Both bad if both outliers

    return df[['Tmax_bad', 'Tmin_bad']]

def fill_T_nldas(snotel_data: pd.Series, nldas_data: pd.Series) -> pd.Series:
    '''
    Fill Tmax or Tmin gaps with NLDAS data. Note, all bad data should be removed prior to this step. 
    '''
    # Ensure snotel data is daily
    snotel_data = snotel_data.asfreq('D')

    # Adjust timezone if needed (e.g., for MST, UTC-7)
    nldas_snoteltz = nldas_data.tz_convert(snotel_data.index.tz)

    # Calculate daily max and min temperatures from hourly NLDAS data
    nldas_daily = nldas_snoteltz.resample('D').agg({'Tair': ['max', 'min']})
    nldas_daily = nldas_daily - 273.15  # Convert from Kelvin to Celsius

    # Rename columns for clarity
    nldas_daily.columns = ['Tair_max', 'Tair_min']

    # Merge SNOTEL and NLDAS temperatures for analysis
    merged_temps = pd.merge(snotel_data[['TTmax', 'TTmin']], nldas_daily[['Tair_max', 'Tair_min']], left_index=True, right_index=True, how='inner')

    # Calculate difference between SNOTEL and NLDAS temperatures
    merged_temps['T_max_diff'] = merged_temps['TTmax'] - merged_temps['Tair_max']
    merged_temps['T_min_diff'] = merged_temps['TTmin'] - merged_temps['Tair_min']

    # Calculate average differences
    avg_max_diff = merged_temps['T_max_diff'].mean()
    avg_min_diff = merged_temps['T_min_diff'].mean()

    # Fill missing SNOTEL Tmax and Tmin with adjusted NLDAS values
    snotel_data['TTmax'] = snotel_data['TTmax'].fillna(nldas_daily['Tair_max'] + avg_max_diff)
    snotel_data['TTmin'] = snotel_data['TTmin'].fillna(nldas_daily['Tair_min'] + avg_min_diff)

    return merged_temps
