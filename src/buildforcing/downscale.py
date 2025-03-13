'''
Functions used to downscale NLDAS data for use with point modeling.
'''
import pandas as pd
from zoneinfo import ZoneInfo


def downscaleTair(nldas_Tair_K: pd.Series, snotel_Tmax_C: pd.Series, snotel_Tmin_C: pd.Series, snotel_tz: ZoneInfo) -> pd.Series:
    '''
    Downscale the NLDAS temperature data to the Snotel site using snotel max and min temperature data.
    This expects the snotel data to have a datetime index as is the case when the data is loaded.
    NLDAS data is expected to have a timezone aware datetime index in UTC.

    Output is in K with UTC timezone as per the target dataframe.

    '''
    # Check if nldas is localized, if not set to UTC
    if nldas_Tair_K.index.tz is None:
        nldas_Tair_K.index = nldas_Tair_K.index.tz_localize('UTC')
    
    # Convert to snotel timezone
    nldas_Tair_K = nldas_Tair_K.tz_convert(snotel_tz)

    # Convert snotel temperatures to K
    snotel_Tmax_K = snotel_Tmax_C + 273.15
    snotel_Tmin_K = snotel_Tmin_C + 273.15

    # Find the index of the max and min temperatures by day, because I need to know the time of day
    nldas_max_idx = nldas_Tair_K.groupby(nldas_Tair_K.index.date).idxmax()
    nldas_min_idx = nldas_Tair_K.groupby(nldas_Tair_K.index.date).idxmin()

    # 

