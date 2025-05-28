'''
Update an attribute of a variable in a netCDF file.
'''
from netCDF4 import Dataset
import argparse

# Read in path to netCDF file, variable name, attribute name, and new value from command line arguments
parser = argparse.ArgumentParser(description="Update an attribute of a variable in a netCDF file.")
parser.add_argument('-f', '--file', required=True, help="Path to the netCDF file")
parser.add_argument('-v', '--variable', required=True, help="Name of the variable to update")
parser.add_argument('-a', '--attribute', required=True, help="Name of the attribute to update")
parser.add_argument('-n', '--new_value', required=True, help="New value for the attribute")
args = parser.parse_args()

file_path = args.file
variable_name = args.variable
attribute_name = args.attribute
new_value = args.new_value

print(f"Updating attribute '{attribute_name}' for variable '{variable_name}' in file: {file_path}")

# Open the netCDF file in append mode
with Dataset(file_path, 'a') as ds:
    if variable_name in ds.variables:
        var = ds.variables[variable_name]
        setattr(var, attribute_name, new_value)
        print(f"Updated '{attribute_name}' attribute to: {new_value}")
    else:
        print(f"Variable '{variable_name}' not found in the netCDF file.")