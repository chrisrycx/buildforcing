'''
Quick test script for earthdata token retrieval and API access.
'''
from buildforcing.datasets import siteNLDAS
from datetime import datetime
import os

dummySite = siteNLDAS('Quemazon', start_date=datetime.now(), end_date=datetime.now(), storage_path=os.environ['NLDAS_PATH'])

token = dummySite.getAPIToken(refresh=False)
print(f"Retrieved token: {token}")

# Test a data request
#dummySite.session.headers.update({'authorization': f'Bearer {token}'})
dummySite.session.headers.update({'authorizationtoken': token})
dummySite.latitude = 35.98  # Example latitude
dummySite.longitude = -109.50  # Example longitude
data = dummySite.getforcing('Tair', datetime(2020, 1, 1), datetime(2020, 1, 2))
print(data.head())