# Data Processing Scripts

## Realtime Data

The realtime data will be processed in three ways:
1. 48hr rolling files - 30 minute cronjob
2. Daily history - daily cronjob
3. Manual timespan - call 'realtime.sh' with specified start and end times

## Files
* *kml_tools.py* is a module containing classes and functions to write kml/kmz files
  - [ ] Add Lixin's improved colour bars
* *sunrise.py* contains functions for generating all realtime plots and kmz files
  - [ ] Add ADCP vectors
  - [ ] Add wind vectors
  - [ ] Add salinity gradient
* *realtime.py* Reads in a YAML file requesting realtime data plots and then calls the relevant functions from sunrise.py
  - [ ] Pat will most likely need to improve
* [ ] Write Lixin's scheduler for the cronjobs

# Packages installed
  - sudo apt install python3-netcdf4
  - sudo apt install python3-gsw
  - sudo apt install python3-geopy
  - python3 -m pip install cmocean
