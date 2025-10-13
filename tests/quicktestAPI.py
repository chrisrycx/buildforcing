'''
Quick test script for earthdata token retrieval and API access.
'''
from buildforcing.datasets import siteNLDAS, PNNLSnotel
from datetime import datetime
import os

# Read in inputs from user: site and forcing version
site_name = input("Enter site name: ")
forcing_version = input("Enter forcing version (e.g., V0, V1): ")

# Verify forcing version is valid
if forcing_version not in ['V0', 'V1']:
    raise ValueError("Invalid forcing version. Please enter 'V0' or 'V1'.")

snotel = PNNLSnotel(site_name, storage_path=os.environ['SNOTEL_PATH'])

dummySite = siteNLDAS(site_name, start_date=datetime.now(), end_date=datetime.now(), storage_path=os.environ['NLDAS_PATH'])
dummySite.latitude = snotel.latitude
dummySite.longitude = snotel.longitude

if forcing_version == 'V0':
    data = dummySite.getforcingV0('Tair', datetime(2020, 1, 1), datetime(2020, 1, 2))
elif forcing_version == 'V1':
    refresh_token = input("Refresh token? (y/n): ").lower() == 'y'
    token = dummySite.getAPIToken(refresh=refresh_token)
    print(f"Retrieved token: {token}")

    #dummySite.session.headers.update({'authorization': f'Bearer {token}'})
    dummySite.session.headers.update({'authorizationtoken': token})
    data = dummySite.getforcingV1('Tair', datetime(2020, 1, 1), datetime(2020, 1, 2))

print(data.head())