'''
Use netCDF4 to inspect a netCDF file and print its contents.
'''
from netCDF4 import Dataset
import argparse

# Read in path to netCDF file from command line argument
parser = argparse.ArgumentParser(description="Inspect a netCDF file.")
parser.add_argument('-f', '--file', required=True, help="Path to the netCDF file")
args = parser.parse_args()

file_path = args.file
print(f"Inspecting netCDF file: {file_path}")

ds = Dataset(file_path, 'r')

# ...existing code...

# Inspect the time variable
time_var_name = None
for var_name, var in ds.variables.items():
    if 'time' in var_name.lower():  # Look for a variable likely representing time
        time_var_name = var_name
        print(f"\nTime variable: {time_var_name}")
        print(f"    Dimensions: {', '.join(var.dimensions)}")
        print(f"    Data type: {var.dtype}")
        for attr_name in var.ncattrs():
            attr_value = getattr(var, attr_name)
            print(f"        {time_var_name}:{attr_name} = {attr_value} ;")
        break

if not time_var_name:
    print("\nNo time variable found in the netCDF file.")

# ...existing code...

# Print dimensions
print("dimensions:")
for dim_name, dim in ds.dimensions.items():
    size = len(dim) if not dim.isunlimited() else "UNLIMITED"
    print(f"    {dim_name} = {size} ;")

# Print variables
print("\nvariables:")
for var_name, var in ds.variables.items():
    dims = ", ".join(var.dimensions)
    print(f"    {var.dtype} {var_name}({dims}) ;")
    for attr_name in var.ncattrs():
        attr_value = getattr(var, attr_name)
        print(f"        {var_name}:{attr_name} = {attr_value} ;")

# Print global attributes
print("\n// global attributes:")
for attr_name in ds.ncattrs():
    attr_value = getattr(ds, attr_name)
    print(f"    :{attr_name} = {attr_value} ;")

