'''
Functions used to downscale NLDAS data for use with point modeling.
'''
import pandas as pd
import numpy as np
from buildforcing.snotelQC import fill_T_nldas, qc_maxmin_temperatures
from buildforcing.metfuncs import calculate_wetbulb, wang2019_snowfrac

def raw_nldas(nldas_data: pd.Series, *args, **kwargs) -> pd.DataFrame:
    '''
    Just a passthru function that accepts a variable number of arguments.
    This will be the default function for downscaling that will just pass the data through when
    another function has not been specified.

    Returns a DataFrame with columns for data and flags.
    '''
    print(f'Using raw NLDAS data for {nldas_data.name}')

    result_df = pd.DataFrame({
        nldas_data.name: nldas_data,
        'flags': 0
    })
    return result_df

def downscaleTairV0(nldas_Tair_K: pd.Series, snotel_Tmax_C: pd.Series, snotel_Tmin_C: pd.Series) -> pd.DataFrame:
    '''
    Downscale the NLDAS temperature data to the Snotel site using snotel max and min temperature data.
    V0 - This algorithm was my first approach to downscaling temperature, it appear problematic in cases.

    ** Note ** Both the NLDAS and Snotel data must have timezone aware datetime indexes. NLDAS data is expected to be in UTC.

    Output is in K with UTC timezone as per the target dataframe.

    Returns a DataFrame with columns for downscaled temperature and flags.

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

    # Create result dataframe
    result_df = pd.DataFrame({
        'Tair': nldas_Tair_K_downscaled,
        'flags': 0
    })

    return result_df

def downscaleTairV1(nldas_Tair_K: pd.Series, snotel_Tmax_C: pd.Series, snotel_Tmin_C: pd.Series) -> pd.DataFrame:
    '''
    Downscale the NLDAS temperature data to the Snotel site using snotel max and min temperature data.

    V1 - This is simply a daily rescaling and shift of the temperatures.

    ** Note ** Both the NLDAS and Snotel data must have timezone aware datetime indexes. NLDAS data is expected to be in UTC.

    Output is in K with UTC timezone as per the target dataframe.

    Returns a DataFrame with columns for downscaled temperature and flags.

    '''
    # Check if the input data is timezone aware
    if nldas_Tair_K.index.tz is None:
        raise ValueError("NLDAS data must be timezone aware (UTC)")
    if snotel_Tmax_C.index.tz is None:
        raise ValueError("Snotel Tmax data must be timezone aware")

    # Convert to snotel timezone
    nldas_Tair_K = nldas_Tair_K.tz_convert(snotel_Tmax_C.index.tz)

    # Quality control the snotel temperature data
    snotel_df = pd.DataFrame({'T_max_C': snotel_Tmax_C, 'T_min_C': snotel_Tmin_C})
    T_qc_flags = qc_maxmin_temperatures(snotel_df, outlier_std=2.5)
    snotel_Tmax_QCd = fill_T_nldas(snotel_df['T_max_C'].where(~T_qc_flags['Tmax_bad']), nldas_Tair_K)
    snotel_Tmin_QCd = fill_T_nldas(snotel_df['T_min_C'].where(~T_qc_flags['Tmin_bad']), nldas_Tair_K)

    # Convert snotel temperatures to K
    snotel_Tmax_K = snotel_Tmax_QCd['T_max_C'] + 273.15
    snotel_Tmin_K = snotel_Tmin_QCd['T_min_C'] + 273.15
    snotel_Tmax_K.name = 'snotel_Tmax'
    snotel_Tmin_K.name = 'snotel_Tmin'

    # Resample the NLDAS data to daily max and min temperatures
    nldas_daily_max = nldas_Tair_K.resample('D').max()
    nldas_daily_min = nldas_Tair_K.resample('D').min()
    nldas_daily_max.name = 'nldas_daily_max'
    nldas_daily_min.name = 'nldas_daily_min'

    # Combine daily values into one dataframe
    daily_data = pd.concat([nldas_daily_max, nldas_daily_min], axis=1)
    daily_data = pd.merge(daily_data, snotel_Tmax_K, how='left', left_index=True, right_index=True)
    daily_data = pd.merge(daily_data, snotel_Tmin_K, how='left', left_index=True, right_index=True)

    # Calculate rescaling and shift factors
    daily_data['rescale'] = (daily_data['snotel_Tmax'] - daily_data['snotel_Tmin']) / (daily_data['nldas_daily_max'] - daily_data['nldas_daily_min'])

    # Join shift and rescale factors to the NLDAS data
    nldas_Tair_K.name = 'nldas_Tair'
    nldas_Tair_K = pd.merge(nldas_Tair_K, daily_data[['rescale', 'nldas_daily_min', 'snotel_Tmin']], how='left', left_index=True, right_index=True)

    # Forward fill NaN values
    nldas_Tair_K = nldas_Tair_K.ffill()

    # Backfill as well if needed
    nldas_Tair_K = nldas_Tair_K.bfill()

    # Finally calculate the downscaled temperature
    nldas_Tair_K['corrected'] = (nldas_Tair_K['nldas_Tair'] - nldas_Tair_K['nldas_daily_min']) * nldas_Tair_K['rescale'] + nldas_Tair_K['snotel_Tmin']
    
    # Generate flags for the downscaled data
    T_qc_flags['flags'] = 0
    T_qc_flags.loc[T_qc_flags['Tmax_bad'] | T_qc_flags['Tmin_bad'], 'flags'] = 2 # Flag as filled data

    # Generate combined output dataframe
    output_df = pd.merge(nldas_Tair_K['corrected'], T_qc_flags['flags'], how='left', left_index=True, right_index=True)
    output_df = output_df.ffill()
    output_df = output_df.rename(columns={'corrected': 'Tair'})

    # Change timezone back to UTC
    output_df = output_df.tz_convert('UTC')

    return output_df

def downscalePrecipV1(nldas_hourly_precip_mm: pd.Series, snotel_daily_precip_mm: pd.Series) -> pd.DataFrame:
    '''
        Downscale the NLDAS precipitation data to the Snotel site using snotel precipitation data.
        Due to differences in precipitation timing between NLDAS and snotel, the correction is based on the monthly
        total precipitation at the Snotel site.

        Pcorrected = Pnldas * (Total Monthly Psnotel / Total Pnldas Monthly)

        Edge Cases:
        If NLDAS has no precipitation for the month, then the corrected precipitation is set to zero.

        Note: Both the NLDAS and Snotel data must have timezone aware datetime indexes. NLDAS data is expected to be in UTC.

        Output is in hourly total precip [mm = kg/m2] with UTC timezone as per the target dataframe.

        Returns a DataFrame with columns for downscaled precipitation and flags.

    '''
    # Check if the input data is timezone aware
    if nldas_hourly_precip_mm.index.tz is None:
        raise ValueError("NLDAS data must be timezone aware (UTC)")
    if snotel_daily_precip_mm.index.tz is None:
        raise ValueError("Snotel precipitation data must be timezone aware")

    # Convert to snotel timezone
    nldas_hourly_precip_mm = nldas_hourly_precip_mm.tz_convert(snotel_daily_precip_mm.index.tz)

    # NLDAS start and end date should be inside the snotel date range
    if nldas_hourly_precip_mm.index.min().date() < snotel_daily_precip_mm.index.min().date():
        raise ValueError("NLDAS data starts before Snotel data")
    if nldas_hourly_precip_mm.index.max().date() > snotel_daily_precip_mm.index.max().date():
        raise ValueError("NLDAS data ends after Snotel data")

    # Track the number of naN values in the snotel data
    snotel_daily_precip_mm.name = 'snotel'
    snotel_daily_df = pd.DataFrame(snotel_daily_precip_mm)
    snotel_daily_df['snotel_nan'] = snotel_daily_df.isna()

    # Resample the NLDAS and Snotel to monthly totals
    nldas_monthly = nldas_hourly_precip_mm.resample('MS').sum()
    snotel_monthly = snotel_daily_df.resample('MS').sum()

    # Merge the monthly data to find the scaling factor
    nldas_monthly.name = 'nldas'
    nldas_monthly_df = pd.merge(nldas_monthly, snotel_monthly, how='left', left_index=True, right_index=True)


    # Perform regression analysis to places where snotel missing data exceeds a threshold
    nan_threshold = 4  # Per month
    if nldas_monthly_df['snotel_nan'].max() > 4:
        # Use only months where number of NaN values is below the threshold
        regression_data = nldas_monthly_df[nldas_monthly_df['snotel_nan'] <= nan_threshold]

        # Perform linear regression using numpy
        slope, intercept = np.polyfit(regression_data['nldas'], regression_data['snotel'], 1)
        linear_model = np.poly1d((slope, intercept))

        # Apply regression model to months where missing data is above the threshold
        # This will replace nldas values with the regression model values and the scale factor will be set to 1 for upscaling
        nldas_monthly_df.loc[nldas_monthly_df['snotel_nan'] > nan_threshold, 'snotel'] = linear_model(nldas_monthly_df['nldas'][nldas_monthly_df['snotel_nan'] > nan_threshold])

    # Calculate the scaling factor
    nldas_monthly_df['scaling_factor'] = nldas_monthly_df['snotel'] / nldas_monthly_df['nldas']

    # Handle edge case - If NLDAS has no precip, scaling factor will be infinity, set to zero
    nldas_monthly_df['scaling_factor'] = nldas_monthly_df['scaling_factor'].replace([np.inf, -np.inf], 0.0)

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

    # Generate flags based on nans in daily snotel data
    nldas_hourly = pd.merge(nldas_hourly, snotel_daily_df['snotel_nan'].astype(int), how='left', left_index=True, right_index=True)
    nldas_hourly['snotel_nan'] = nldas_hourly['snotel_nan'].ffill()
    nldas_hourly['flags'] = 0
    nldas_hourly.loc[nldas_hourly['snotel_nan'] == 1, 'flags'] = 2  # Flag as filled data

    # Change timezone back to UTC
    nldas_hourly = nldas_hourly.tz_convert('UTC')

    return nldas_hourly[['downscaled', 'flags']].rename(columns={'downscaled': 'Rainf'})
    
def partitionPrecipV0(precip_mm: pd.Series, Tair_K: pd.Series) -> pd.DataFrame:
    '''
    Partition precipitation into rain and snow.
    V0: Just partition if Tair >= 0 C, else snow.
    Input indexes must match.

    Output is a DataFrame with columns 'rain_mm', 'rain_flags', 'snow_mm', 'snow_flags'.

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

    # Add flag columns
    data['rain_flags'] = 0
    data['snow_flags'] = 0

    return data[['rain_mm', 'rain_flags', 'snow_mm', 'snow_flags']]

def partitionPrecipV1(precip_mm: pd.Series, Tair_K: pd.Series, Qair: pd.Series, Psurf: pd.Series) -> pd.DataFrame:
    '''
    Partition precipitation into rain and snow.
    V1: use wang2019_snowfrac to determine fraction of snow vs rain.
    Input indexes must match.

    Output is a DataFrame with columns 'rain_mm', 'rain_flags', 'snow_mm', 'snow_flags'.

    '''
    # Change to C from K
    Tair_C = Tair_K - 273.15

    # Check if the input data has the same index
    if not precip_mm.index.equals(Tair_C.index):
        raise ValueError("Precipitation and temperature data must have the same index")
    if not precip_mm.index.equals(Qair.index):
        raise ValueError("Precipitation and Qair data must have the same index")
    if not precip_mm.index.equals(Psurf.index):
        raise ValueError("Precipitation and Psurf data must have the same index")
    
    # Calculate wet-bulb temperature
    Twb_C = calculate_wetbulb(Tair_C.to_numpy(), Qair.to_numpy(), Psurf.to_numpy())

    # Calculate snow fraction using wang2019_snowfrac
    snow_frac = wang2019_snowfrac(Twb_C)

    # Calculate rain fraction
    rain_frac = 1 - snow_frac

    # Calculate rain and snow amounts
    rain_mm = precip_mm * rain_frac
    snow_mm = precip_mm * snow_frac

    # Round data to the nearest 0.01 mm
    rain_mm = rain_mm.round(2)
    snow_mm = snow_mm.round(2)

    # Combine into a DataFrame
    data = pd.DataFrame({
        'rain_mm': rain_mm,
        'snow_mm': snow_mm
    }, index=precip_mm.index)

    # Add flag columns
    data['rain_flags'] = 0
    data['snow_flags'] = 0

    return data[['rain_mm', 'rain_flags', 'snow_mm', 'snow_flags']]

def downscalePressureV0(nldas_Psurf_Pa: pd.Series, Tair_avg_K: pd.Series, snotel_elevation_m: float, nldas_elevation_m: float) -> pd.DataFrame:
    '''
    Downscale pressure following Chen 2024, which appears to use the hydrostatic equation.
    Ideally Tair should be the average temperature between the two elevations in the atmosphere.
    Assumes input data indexes match.

    Returns a DataFrame with columns for downscaled pressure and flags.
    '''
    # Constants
    g = 9.81  # m/s2
    R_d = 287.05  # J/(kg*K)

    # Calculate the pressure at the Snotel site using the hydrostatic equation
    P_snotel = nldas_Psurf_Pa * np.exp(-1*g*(snotel_elevation_m - nldas_elevation_m) / (R_d*Tair_avg_K))

    # Create result dataframe
    result_df = pd.DataFrame({
        'PSurf': P_snotel,  # Stupid bug, this needs to be PSurf to match expected output not Psurf as is used in forcing
        'flags': 0
    })

    return result_df

def getDownscaleFunction(variable_name: str, version: int = 0) -> callable:
    '''
    Get the downscaling function for a given variable name and version.
    Args:
        variable_name (str): The name of the variable to downscale (e.g., 'Tair', 'precip').
        version (int): The version of the downscaling function to use. Defaults to 0.
    '''
    downscale_functions = {
        'Tair': {
            0: raw_nldas,
            1: downscaleTairV1,
        },
        'Rainf': {
            0: raw_nldas,  # No downscaling for Rainf, just pass through
            1: downscalePrecipV1,  # Downscale precipitation using the V1 method
        },
        'precip_partition': {
            0: partitionPrecipV0,  # Partition precipitation using the V0 method
            1: partitionPrecipV1,  # Partition precipitation using the V1 method
        },
        'LWdown': {
            0: raw_nldas,  # No downscaling for LWdown, just pass through
        },
        'SWdown': {
            0: raw_nldas,  # No downscaling for SWdown, just pass through
        },
        'Qair': {
            0: raw_nldas,  # No downscaling for Qair, just pass through
        },
        'Psurf': {
            0: raw_nldas,  # No downscaling for Psurf, just pass through
            1: downscalePressureV0,  # Downscale pressure using the V0 method
        },
        'Wind': {
            0: raw_nldas,  # No downscaling for Wind, just pass through
        }
    }
    if variable_name not in downscale_functions:
        raise ValueError(f"No downscaling function defined for variable '{variable_name}'")
    
    return downscale_functions[variable_name].get(version, raw_nldas)


