# Data Processing Scripts

## Realtime Data

The realtime data will be processed in three ways:
1. 48hr rolling files - 30 minute cronjob
2. Daily history - daily cronjob
3. Manual timespan - call 'realtime.sh' with specified start and end times

## Files
* *kml_tools.py* is a module containing classes and functions to write kml/kmz files
  - [ ] Add Lixin's improved colour bars
* *sections.py* contains a functions for generating two pngs with ADCP velocity and shear sections
  - [ ] Poor Man's Vorticity needs work - in particular least squares does not always converge
* *realtime.sh* calls all the following realtime python subroutines. It is called manually with specified start and end times.
  - [ ] Pat will replace
* [ ] Write Lixin's scheduler for the cronjobs

# Realtime Python Subroutines
* *throughflow.py* creates kmz files of salinity, temperature, and density from the throughflow data. Only the Pelican throughflow is implemented at the moment.
  - [ ] Add Walton Smith throughflow. Are the issues with the file headers sorted?
  - [ ] Add ASV throughflow
  - [ ] Should we implement these kmz files using network links?
  - [ ] Make png versions of the kml/kmz files
* *Pelican_ADCP_sections.py* creates ADCP sections from the Pelican data using function in *section.py*
* [ ] ADCP sections - I'm writing these now (13/06/2021)
  - I'm going to make these three seperate subroutines for the Pelican, Walton Smith, and the ASVs since it will be useful to be able to call them individually.
* [ ] ADCP vectors

All python subroutines should accept 3 system arguments: start, end, directory. 
Start and end should be timestrings in isoformat 'YYYY-mm-ddTHH:MM:SS' or 'YYYY-mm-ddTHH:MM:SSzzzzzz'.
The former is UTC assumed.
