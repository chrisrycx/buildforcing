import os
import xarray as xr
from pathlib import Path
from buildforcing.datasets import siteNLDAS, PNNLSnotel

# Use NLDAS path from environment variable
nldas_path = os.getenv('NLDAS_PATH')  # type: ignore
snotel_path = os.getenv('SNOTEL_PATH')  # type: ignore
if nldas_path is None or snotel_path is None:
    raise EnvironmentError("NLDAS_PATH or SNOTEL_PATH environment variable is not set.")

# Convert string paths to Path objects
nldas_directory = Path(nldas_path)

# Find all .nc files
nc_files = list(nldas_directory.glob("*.nc"))
print(f"Found {len(nc_files)} .nc files")

for nc_file in nc_files:
    filename = nc_file.stem  # Get filename without extension

    # Split by underscore and check first three parts
    parts = filename.split('_')
    if len(parts) < 5:
        print(f"Skipping {nc_file.name}: not enough parts")
        continue

    # Check if first part is 'NLDAS'
    if parts[0] != 'NLDAS':
        print(f"Skipping {nc_file.name}: first part is not 'NLDAS'")
        continue

    # Try to parse next two parts as floats
    try:
        latitude = float(parts[1])
        longitude = float(parts[2])
        startdate_str = parts[3]
        enddate_str = parts[4]
    except ValueError:
        print(f"Skipping {nc_file.name}: parts 2 and 3 are not floats")
        continue

    print(f"Processing {nc_file.name}...")

    # Search snotel summary file for matching lat/long
    summary_file = os.path.join(snotel_path, 'bcqc_data_v2', 'SNOTEL_summary.csv')
    snotel_name = ''
    with open(summary_file) as f:
        for line in f:
            # Remove \n from the line
            line = line.strip()
            column_values = line.split(',')
            # Latitude and longitude are in columns 5 and 6 (0-indexed)
            try:
                snotel_lat = float(column_values[5])
                snotel_lon = float(column_values[6])
            except ValueError:
                continue

            if abs(snotel_lat - latitude) < 0.01 and abs(snotel_lon - longitude) < 0.01:
                snotel_name = column_values[3]
                print(f"  Found matching SNOTEL site: {snotel_name}")
                break

    if snotel_name == '':
        print(f"  No matching SNOTEL site found for lat {latitude}, lon {longitude}")
        continue

    # Load the snotel data for the site
    snotel = PNNLSnotel(snotel_name, snotel_path)

    # Check if precise snotel location is close enough to NLDAS location
    if snotel.precise_location:
        if abs(snotel.latitude - latitude) > 0.01 or abs(snotel.longitude - longitude) > 0.01:
            print(f"Existing NLDAS location ({latitude}, {longitude}) is not close to precise SNOTEL location ({snotel.latitude}, {snotel.longitude}).")
            continue

    # Get elevation information from NLDAS elevation file
    nldas = siteNLDAS(snotel_name, snotel.latitude, snotel.longitude, start_date=snotel.start_date, end_date=snotel.end_date, storage_path=nldas_path)
    nldas.getNLDASElevation()

    print(f"  SNOTEL Elevation: {snotel.elevation} m")
    print(f"  NLDAS Elevation: {nldas.elevation} m")

    # Open the file with xarray
    ds = xr.open_dataset(nc_file)

    # # Add elevation variable with value
    ds['elevation'] = ds['elevation'] = xr.DataArray(nldas.elevation, attrs={'units': 'm', 'long_name': 'elevation'})

    # # Save back to the new file
    new_file_name = f"NLDAS_{nldas.snotel_filename}_{startdate_str}_{enddate_str}.nc"
    output_path = nc_file.parent / new_file_name
    ds.to_netcdf(output_path)
    ds.close()

