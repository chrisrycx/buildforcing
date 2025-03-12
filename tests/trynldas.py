'''
A quick initial test of the NLDAS class.
'''

from buildforcing.datasets import PNNLSnotel, siteNLDAS
from datetime import datetime

# Create an instance of the PNNLSnotel class
snotel = PNNLSnotel('Temple Fork')

if snotel.exists:
    nldas = siteNLDAS(snotel)
    nldas.getdata('Tair', datetime(2010,1,1), datetime(2010,1,2))
    print(nldas.data.head())
  