'''
Functions used to downscale NLDAS data for use with point modeling.
'''
import pandas as pd


def downscaleTairV0(nldas_Tair_K: pd.Series, snotel_Tmax_C: pd.Series, snotel_Tmin_C: pd.Series) -> pd.Series:
    '''
    Downscale the NLDAS temperature data to the Snotel site using snotel max and min temperature data.
    V0 - This algorithm was my first approach to downscaling temperature, it appear problematic in cases.

    ** Note ** Both the NLDAS and Snotel data must have timezone aware datetime indexes. NLDAS data is expected to be in UTC.

    Output is in K with UTC timezone as per the target dataframe.

    '''
    # Check if the input data is timezone aware
    if nldas_Tair_K.index.tz is None:
        raise ValueError("NLDAS data must be timezone aware (UTC)")
    if snotel_Tmax_C.index.tz is None:
        raise ValueError("Snotel Tmax data must be timezone aware")
    
    # Convert to snotel timezone
    nldas_Tair_K = nldas_Tair_K.tz_convert(snotel_Tmax_C.index.tz)

    # Convert snotel temperatures to K
    snotel_Tmax_K = snotel_Tmax_C + 273.15
    snotel_Tmin_K = snotel_Tmin_C + 273.15

    # Linearly interpolate any missing values in the snotel data
    snotel_Tmax_K = snotel_Tmax_K.interpolate()
    snotel_Tmin_K = snotel_Tmin_K.interpolate()

    # Find the index of the max and min temperatures by day, because I need to know the time of day
    nldas_max_idx = nldas_Tair_K.groupby(nldas_Tair_K.index.date).idxmax()
    nldas_min_idx = nldas_Tair_K.groupby(nldas_Tair_K.index.date).idxmin()
    nldas_max = nldas_Tair_K.loc[nldas_max_idx]
    nldas_min = nldas_Tair_K.loc[nldas_min_idx]

    # Get the associated snotel max and min temperatures
    nldas_dates = nldas_max.index.normalize()
    snotel_max = snotel_Tmax_K.loc[nldas_dates]
    snotel_min = snotel_Tmin_K.loc[nldas_dates]

    # Calculate the difference, always nldas - snotel so that the shift is consistent
    diff_max = pd.Series(snotel_max.to_numpy() - nldas_max.to_numpy(), index = nldas_max.index)
    diff_min = pd.Series(snotel_min.to_numpy() - nldas_min.to_numpy(), index = nldas_min.index)
    snotel_diffs = pd.concat([diff_max, diff_min], axis=0)
    snotel_diffs = snotel_diffs.sort_index()

    # Merge the differences back into the original NLDAS data
    snotel_diffs.name = 'snotel_diffs'
    nldas_Tair_K.name = 'Tair'
    nldas_Tair_k_df = pd.merge(nldas_Tair_K, snotel_diffs, how='left', left_index=True, right_index=True)

    # If the first or last endpoints are missing, set to zero
    if pd.isna(nldas_Tair_k_df['snotel_diffs'].iloc[0]):
        nldas_Tair_k_df.loc[nldas_Tair_k_df.index[0],'snotel_diffs'] = 0
    if pd.isna(nldas_Tair_k_df['snotel_diffs'].iloc[-1]):
        nldas_Tair_k_df.loc[nldas_Tair_k_df.index[-1],'snotel_diffs'] = 0

    # Interpolate the missing values in diffs
    nldas_Tair_k_df['snotel_diffs'] = nldas_Tair_k_df['snotel_diffs'].interpolate()

    # Finally calculate the downscaled temperature
    nldas_Tair_K_downscaled = nldas_Tair_k_df['Tair'] + nldas_Tair_k_df['snotel_diffs']

    # Change timezone back to UTC
    nldas_Tair_K_downscaled = nldas_Tair_K_downscaled.tz_convert('UTC')

    return nldas_Tair_K_downscaled

def downscaleTairV1(nldas_Tair_K: pd.Series, snotel_Tmax_C: pd.Series, snotel_Tmin_C: pd.Series) -> pd.Series:
    '''
    Downscale the NLDAS temperature data to the Snotel site using snotel max and min temperature data.

    V1 - This is simply a daily rescaling and shift of the temperatures.

    ** Note ** Both the NLDAS and Snotel data must have timezone aware datetime indexes. NLDAS data is expected to be in UTC.

    Output is in K with UTC timezone as per the target dataframe.

    '''
    # Check if the input data is timezone aware
    if nldas_Tair_K.index.tz is None:
        raise ValueError("NLDAS data must be timezone aware (UTC)")
    if snotel_Tmax_C.index.tz is None:
        raise ValueError("Snotel Tmax data must be timezone aware")
    
    # Convert to snotel timezone
    nldas_Tair_K = nldas_Tair_K.tz_convert(snotel_Tmax_C.index.tz)

    # Convert snotel temperatures to K
    snotel_Tmax_K = snotel_Tmax_C + 273.15
    snotel_Tmin_K = snotel_Tmin_C + 273.15
    snotel_Tmax_K.name = 'snotel_Tmax'
    snotel_Tmin_K.name = 'snotel_Tmin'

    # Resample the NLDAS data to daily max and min temperatures
    nldas_daily_max = nldas_Tair_K.resample('D').max()
    nldas_daily_min = nldas_Tair_K.resample('D').min()
    nldas_daily_max.name = 'nldas_daily_max'
    nldas_daily_min.name = 'nldas_daily_min'

    # Linearly interpolate any missing values in the snotel data
    snotel_Tmax_K = snotel_Tmax_K.interpolate()
    snotel_Tmin_K = snotel_Tmin_K.interpolate()

    # Combine daily values into one dataframe
    daily_data = pd.concat([nldas_daily_max, nldas_daily_min], axis=1)
    daily_data = pd.merge(daily_data, snotel_Tmax_K, how='left', left_index=True, right_index=True)
    daily_data = pd.merge(daily_data, snotel_Tmin_K, how='left', left_index=True, right_index=True)

    # Calculate rescaling and shift factors
    daily_data['rescale'] = (daily_data['snotel_Tmax'] - daily_data['snotel_Tmin']) / (daily_data['nldas_daily_max'] - daily_data['nldas_daily_min'])
    daily_data['shift'] = daily_data['snotel_Tmin'] - daily_data['nldas_daily_min']

    # Join shift and rescale factors to the NLDAS data
    nldas_Tair_K.name = 'nldas_Tair'
    nldas_Tair_K = pd.merge(nldas_Tair_K, daily_data[['rescale', 'shift']], how='left', left_index=True, right_index=True)

    # Forward fill NaN values in rescale and shift
    nldas_Tair_K['rescale'] = nldas_Tair_K['rescale'].ffill()
    nldas_Tair_K['shift'] = nldas_Tair_K['shift'].ffill()

    # Finally calculate the downscaled temperature
    nldas_Tair_K['corrected'] = nldas_Tair_K['nldas_Tair'] * nldas_Tair_K['rescale'] + nldas_Tair_K['shift']
    nldas_Tair_K_downscaled = nldas_Tair_K['corrected']

    # Change timezone back to UTC
    nldas_Tair_K_downscaled = nldas_Tair_K_downscaled.tz_convert('UTC')

    return nldas_Tair_K_downscaled

def downscalePrecip(nldas_hourly_precip_mm: pd.Series, snotel_daily_precip_mm: pd.Series) -> pd.Series:
    '''
    Downscale the NLDAS precipitation data to the Snotel site using snotel precipitation data.
    Due to differences in precipitation timing between NLDAS and snotel, the correction is based on the monthly
    total precipitation at the Snotel site.

    Pcorrected = Pnldas * (Total Monthly Psnotel / Total Pnldas Monthly)

    Edge Cases:
    If Snotel has significant precipitation but NLDAS does not, set to zero (**Improve this**)
    If NLDAS has significant precipitation but Snotel does not, set to zero (**Improve this**)

    Note: Both the NLDAS and Snotel data must have timezone aware datetime indexes. NLDAS data is expected to be in UTC.

    Output is in hourly total precip [mm = kg/m2] with UTC timezone as per the target dataframe.

    '''
    # Check if the input data is timezone aware
    if nldas_hourly_precip_mm.index.tz is None:
        raise ValueError("NLDAS data must be timezone aware (UTC)")
    if snotel_daily_precip_mm.index.tz is None:
        raise ValueError("Snotel precipitation data must be timezone aware")
    
    # Convert to snotel timezone
    nldas_hourly_precip_mm = nldas_hourly_precip_mm.tz_convert(snotel_daily_precip_mm.index.tz)

    # Replace any Snotel NaN values with 0.0
    snotel_daily_precip_mm = snotel_daily_precip_mm.fillna(0.0)

    # Resample nldas to daily totals
    # This is needed to ensure the 30day resampling aligns with the snotel data
    nldas_daily = nldas_hourly_precip_mm.resample('D').sum()
    snotel_daily_subset = snotel_daily_precip_mm.loc[nldas_daily.index]

    # Resample the NLDAS and Snotel to monthly totals
    nldas_monthly = nldas_hourly_precip_mm.resample('30D').sum()
    snotel_monthly = snotel_daily_subset.resample('30D').sum()

    # Merge the monthly data to find the scaling factor
    nldas_monthly.name = 'nldas_monthly'
    snotel_monthly.name = 'snotel_monthly'
    nldas_monthly_df = pd.merge(nldas_monthly, snotel_monthly, how='left', left_index=True, right_index=True)
    nldas_monthly_df['scaling_factor'] = nldas_monthly_df['snotel_monthly'] / nldas_monthly_df['nldas_monthly']

    # Handle edge cases
    nldas_monthly_df['scaling_factor'] = nldas_monthly_df['scaling_factor'].where(nldas_monthly_df['nldas_monthly'] >= 0.5, 0.0)  # Potentially no precip in NLDAS
    nldas_monthly_df['scaling_factor'] = nldas_monthly_df['scaling_factor'].where(nldas_monthly_df['snotel_monthly'] > 0, 0.0)  # Potentially no precip in Snotel

    # Upscale the scaling factor to hourly data
    # This is done by repeating the monthly scaling factor for each hour in the month
    nldas_scaling_factor = nldas_monthly_df['scaling_factor'].resample('h').ffill()
    nldas_scaling_factor.name = 'scaling_factor'

    # Create a dataframe with the scaling factor for each hour
    nldas_hourly_precip_mm.name = 'nldas_hourly'
    nldas_hourly = pd.merge(nldas_hourly_precip_mm, nldas_scaling_factor, how='left', left_index=True, right_index=True)
    
    # Forward fill the scaling factor to fill in any missing values
    # This is required even when upsampling the scaling factor to hourly data because the upsampled data may not have the same index as the original data
    nldas_hourly['scaling_factor'] = nldas_hourly['scaling_factor'].ffill()

    # Multiply the NLDAS hourly data by the scaling factor for each hour
    nldas_hourly['downscaled'] = nldas_hourly['nldas_hourly'] * nldas_hourly['scaling_factor']

    # Change timezone back to UTC
    nldas_hourly = nldas_hourly.tz_convert('UTC')

    return nldas_hourly['downscaled']

def partitionPrecip(precip_mm: pd.Series, Tair_K: pd.Series) -> pd.DataFrame:
    '''
    Partition precipitation into rain and snow.
    V0: Just partition if Tair >= 0 C, else snow.
    Input indexes must match.

    Output is a DataFrame with columns 'rain_mm' and 'snow_mm'.

    '''
    # Change to C from K
    Tair_C = Tair_K - 273.15

    # Check if the input data has the same index
    if not precip_mm.index.equals(Tair_C.index):
        raise ValueError("Precipitation and temperature data must have the same index")

    # Combine the input data into a DataFrame
    data = pd.concat([precip_mm, Tair_C], axis=1)
    data.columns = ['precip_mm', 'Tair_C']
    
    # Partition the precipitation
    data['rain_mm'] = data['precip_mm'].where(data['Tair_C'] >= 0, 0)
    data['snow_mm'] = data['precip_mm'].where(data['Tair_C'] < 0, 0)

    return data[['rain_mm', 'snow_mm']]


