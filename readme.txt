Version History:
Version 0.11.1 - 2026-03-02 - Added more unit testing to wetbulb calcs, changed to just using sat vapor over liquid.
Version 0.11.0 - 2026-02-24 - Added partition method v2 which is Wang but limited by Jordan
Version 0.10.3 - 2025-11-04 - Fixed bug in precipitation downscaling where negative values could occur after regression step.
Version 0.10.2 - 2025-11-02 - Fixed bug in precipitation downscaling where 0 precip lead to Nan values.
Version 0.10.1 - 2025-11-02 - Fixed bug in temperature downscaling where Nans in flags not handled correctly at start/end of time series.
Version 0.10.0 - 2025-11-01 - Add new precipitation partitioning method (V1) that uses wetbulb temperature for better accuracy.
Version 0.9.1 - 2025-10-29 - Fix minor bug and warning
Version 0.9.0 - 2025-10-29 - Add flagging variables to output
Version 0.8.4 - 2025-10-18 - Fall back to loading elevation data from file if not in netCDF, also fixed minor bug with downscale functions
Version 0.8.3 - 2025-10-16 - Fixed bug where precise location data had Nan values and would crash the program.
Version 0.8.2 - 2025-10-15 - Fixed bug where elevation wasn't being saved when downloading data
version 0.8.1 - 2025-10-13 - Add option for using old NLDAS API (v0) as a backup.
Version 0.8.0 - 2025-10-? - Updated NLDAS API endpoint and algorithm
Version 0.7.3 - 2025-10-10 - Fixed bug in pressure correction where elevation argument name was incorrect.
Version 0.7.2 - 2025-10-06 - Pressure downscaling implemented.
Version 0.7.1 - 2025-10-01 - Added more precise snotel location data from Detre dataset. Changed how NLDAS files are named.
Version 0.7.0 - 2025-09-30 - Redesigned how gap filling is handled in temperature and precipitation. Added temperature QC.
Version 0.6.0 - 2025-08-05 - Added 1 day limit to interpolation in temperature downloaded and tested.
Version 0.5.1 - 2025-08-04 - Added a utility script for outputting settings order to command line.
Version 0.5.0 - 2025-07-30 - Multiple changes to how dates are handled so that both snotel and nldas date ranges are as expected.
Version 0.4.6 - 2025-07-30 - Fixed bug in PNNLSnotel where it was not loading data correctly. Also changed how dates are handled in nldas and site forcings.
Version 0.4.5 - 2025-07-29 - Changed PNNLSnotel to use siteNLDAS so that snotel doesn't load data by default and nldas looks for existing files encompassing the date range.
Version 0.4.4 - 2025-06-04 - Implemented setting string for buildsite
Version 0.4.3 - 2025-05-28 - Remove netCDF calendar encoding. Now will default to proleptic Gregorian calendar.
Version 0.4.2 - 2025-05-27 - Try exporting to julian calendar
Version 0.4.1 - 2025-05-23 - Improved request to NLDAS API, now has retries and chunking to prevent no data being returned.
Version 0.4.0 - 2025-05-19 - Changed buildforcing to a class.
Version 0.3.2 - 2025-05-09 - Fixed problem if snotel does not contain usable data for specified time range.
Version 0.3.1 - 2025-05-08 - Moved buildsite test out of script to fix potential linux issue.
Version 0.3.0 - 2025-05-07 - Add version 1 of temperature downscaling for testing
Version 0.2.0 - 2025-04-29 - Changed precipitation downscaling to use 30 day sum for scaling.
Version 0.1.0 - 2025-04-22 - Basic algorithm in place for all variables. Output should make sense, but still use for testing until methods are validated.
Version 0.0.0 - 2025-04-08 - All variables downloaded from NLDAS but corrections not applied yet in most cases. Don't use for real model runs.
