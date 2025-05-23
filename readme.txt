Version History:
Version 0.4.1 - 2025-05-23 - Improved request to NLDAS API, now has retries and chunking to prevent no data being returned.
Version 0.4.0 - 2025-05-19 - Changed buildforcing to a class.
Version 0.3.2 - 2025-05-09 - Fixed problem if snotel does not contain usable data for specified time range.
Version 0.3.1 - 2025-05-08 - Moved buildsite test out of script to fix potential linux issue.
Version 0.3.0 - 2025-05-07 - Add version 1 of temperature downscaling for testing
Version 0.2.0 - 2025-04-29 - Changed precipitation downscaling to use 30 day sum for scaling.
Version 0.1.0 - 2025-04-22 - Basic algorithm in place for all variables. Output should make sense, but still use for testing until methods are validated.
Version 0.0.0 - 2025-04-08 - All variables downloaded from NLDAS but corrections not applied yet in most cases. Don't use for real model runs.
