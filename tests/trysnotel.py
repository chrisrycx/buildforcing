'''
A quick initial test of the PNNLSnotel class.
'''
from buildforcing.datasets import PNNLSnotel

# Create an instance of the PNNLSnotel class
snotel = PNNLSnotel('TonyGrove')

if snotel.exists:
    snotel.data.head()