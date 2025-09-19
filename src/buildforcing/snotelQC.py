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
    # Remove NaN values before calculating statistics
    data_clean = data[~np.isnan(data)]
    median = np.median(data_clean)
    std_dev = np.std(data_clean)
    upper_limit = median + sigma_threshold * std_dev
    lower_limit = median - sigma_threshold * std_dev
    return (data > upper_limit) | (data < lower_limit)

def detrend_seasonal_cycle(data: pd.Series) -> np.ndarray:
    '''
    Use a best fit sinusoid to detrend seasonal cycle from data.
    y = B0 + B1*sin(2*pi*t/365) + B2*cos(2*pi*t/365)
    Input:
    data (pd.Series): Time series data with a DateTime index.
    Output:
    np.ndarray: Detrended data array.
    '''

    # Ensure data has no missing values
    data_clean = data.dropna()

    # Get the days since the start of the series
    t = (data_clean.index - data_clean.index[0]).days.to_numpy()
    y = data_clean.to_numpy()
    # Construct the design matrix
    A = np.vstack([np.ones(len(t)), np.sin(2 * np.pi * t / 365), np.cos(2 * np.pi * t / 365)]).T
    # Solve for coefficients using least squares
    coeffs, _, _, _ = np.linalg.lstsq(A, y, rcond=None)

    # Calculate the fitted seasonal cycle on the original data's index
    t2 = (data.index - data.index[0]).days.to_numpy()
    A2 = np.vstack([np.ones(len(t2)), np.sin(2 * np.pi * t2 / 365), np.cos(2 * np.pi * t2 / 365)]).T
    seasonal_cycle = A2 @ coeffs

    # Detrend the data
    detrended = data.to_numpy() - seasonal_cycle
    return detrended

def qc_maxmin_temperatures(df: pd.DataFrame, outlier_std: float=3.0) -> pd.DataFrame:
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
    df['Tmax_outlier'] = check_outliers(detrend_seasonal_cycle(df['Tmax']), sigma_threshold=outlier_std)
    df['Tmin_outlier'] = check_outliers(detrend_seasonal_cycle(df['Tmin']), sigma_threshold=outlier_std)
    # Check for inconsistent Tmax/Tmin pairs
    df['Tmax_Tmin_inconsistent'] = df['Tmax'] < df['Tmin']
    # Calculate Diurnal Temperature Range (DTR)
    df['DTR'] = df['Tmax'] - df['Tmin']
    # Check for outliers in DTR
    df['DTR_outlier'] = check_outliers(df['DTR'].to_numpy())

    # Interpret the flags
    df['Tmax_bad'] = False
    df['Tmin_bad'] = False
    df.loc[df['Tmax_Tmin_inconsistent'], ['Tmax_bad', 'Tmin_bad']] = True # Both bad if inconsistent
    df.loc[df['Tmax_outlier'], 'Tmax_bad'] = True
    df.loc[df['Tmin_outlier'], 'Tmin_bad'] = True

    # DTR should be larger then 3C
    df.loc[df['DTR'] < 3, ['Tmax_bad', 'Tmin_bad']] = True

    return df[['Tmax_bad', 'Tmin_bad']]

def fill_T_nldas(snotel_data: pd.Series, nldas_T_data: pd.Series) -> pd.DataFrame:
    '''
    Fill Tmax or Tmin gaps with NLDAS data. Note, all bad data should be removed prior to this step. 

    Input:
    snotel_data (pd.Series): SNOTEL temperature data (Tmax or Tmin), daily frequency, local timezone.
    nldas_T_data (pd.Series): NLDAS temperature data (hourly), UTC timezone, degrees K.
    T_type (str): 'max' or 'min' to indicate which temperature type is being filled.

    Output DataFrame with columns [<input>, 'nldas_filled']
    '''
    # Get temperature type from snotel_data name
    column_name = snotel_data.name
    T_type = 'max' if 'T_max_C' == snotel_data.name else 'min' if 'T_min_C' == snotel_data.name else None
    if T_type is None:
        raise ValueError("snotel_data name must contain 'T_max_C' or 'T_min_C'.")

    # Ensure snotel data is daily
    snotel_data = snotel_data.asfreq('D')

    # Adjust timezone if needed (e.g., for MST, UTC-7)
    nldas_snoteltz = nldas_T_data.tz_convert(snotel_data.index.tz)

    # Calculate daily max and min temperatures from hourly NLDAS data
    nldas_daily = nldas_snoteltz.resample('D').agg(T_type)
    nldas_daily = nldas_daily - 273.15  # Convert from Kelvin to Celsius
    nldas_daily.name = 'nldas'

    # Merge SNOTEL and NLDAS temperatures for analysis
    snotel_data.name = 'snotel'
    merged_temps = pd.merge(snotel_data, nldas_daily, left_index=True, right_index=True, how='inner')

    # Calculate difference between SNOTEL and NLDAS temperatures
    merged_temps['T_diff'] = merged_temps['nldas'] - merged_temps['snotel']

    # Calculate average differences
    avg_diff = merged_temps['T_diff'].mean()

    # Fill missing SNOTEL data with NLDAS data adjusted by average difference
    snotel_data_filled = snotel_data.fillna(merged_temps['nldas'] - avg_diff)

    # Create a dataframe with filled data and flags indicating filled values
    snotel_data_filled = pd.DataFrame({
        column_name: snotel_data_filled,
        'filled_flag': snotel_data.isna()  # True where data was filled
    })

    return snotel_data_filled
