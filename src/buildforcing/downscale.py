'''
Functions used to downscale NLDAS data for use with point modeling.
'''
import pandas as pd


def downscaleTair(nldas_Tair_K: pd.Series, snotel_Tmax_C: pd.Series, snotel_Tmin_C: pd.Series) -> pd.Series:
    '''
    Downscale the NLDAS temperature data to the Snotel site using snotel max and min temperature data.

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

def downscalePrecip(nldas_hourly_precip_mm: pd.Series, snotel_daily_precip_mm: pd.Series) -> pd.Series:
    '''
    Downscale the NLDAS precipitation data to the Snotel site using snotel precipitation data.

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

    # Resample the NLDAS data to daily totals
    nldas_daily = nldas_hourly_precip_mm.resample('D').sum()

    # Find a scaling factor for each day
    nldas_daily.name = 'nldas_daily'
    snotel_daily_precip_mm.name = 'snotel_daily'
    nldas_daily_df = pd.merge(nldas_daily, snotel_daily_precip_mm, how='left', left_index=True, right_index=True)
    nldas_daily_df['scaling_factor'] = nldas_daily_df['snotel_daily'] / nldas_daily_df['nldas_daily']

    # Merge scaling factor back into the original NLDAS data
    nldas_hourly_precip_mm.name = 'nldas_hourly'
    nldas_hourly = pd.merge(nldas_hourly_precip_mm, nldas_daily_df[['scaling_factor']], how='left', left_index=True, right_index=True)
    nldas_hourly['scaling_factor'] = nldas_hourly['scaling_factor'].ffill()

    # Multiply the NLDAS hourly data by the scaling factor for each day
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


