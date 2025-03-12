'''
Functions used to downscale NLDAS data for use with point modeling.
'''
import pandas as pd


def downscaleTair(nldas_Tair_K: pd.Series, snotel_Tmax_C: pd.Series, snotel_Tmin_C: pd.Series, snotel_tz) -> pd.Series:
    '''
    Downscale the NLDAS temperature data to the Snotel site using snotel max and min temperature data.
    This expects the snotel data to have a datetime index as is the case when the data is loaded.
    NLDAS data is expected to have a timezone aware datetime index in UTC.

    Output is in K with UTC timezone as per the target dataframe.

    '''
    # Calculate the difference between the NLDAS and Snotel temperature data
    delta = nldas['Tair'] - snotel['T_avg_F']
    
    # Add the difference to the NLDAS temperature data
    nldas['Tair'] = snotel['T_avg_F'] + delta
    
    return nldas