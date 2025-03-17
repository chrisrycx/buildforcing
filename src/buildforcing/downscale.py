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

