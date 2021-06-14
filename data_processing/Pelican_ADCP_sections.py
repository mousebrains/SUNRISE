import netCDF4
import datetime
import numpy as np
import cmocean.cm as cmo
import sys
import os
from geopy.distance import distance

import sections

# *************************** PARSE SYSTEM ARGS *************************** #

START = sys.argv[1]
END = sys.argv[2]
WRITE_DIRECTORY = sys.argv[3]

try:
    if START == "None":
        start = datetime.datetime.fromisoformat("2021-06-19T00:00:00+00:00")
    else:
        start = datetime.datetime.fromisoformat(START)
    if start.tzinfo is None:
        start = start.replace(tzinfo=datetime.timezone.utc)
except:
    sys.exit("Invalid start time. Start time must be in isoformat: \n" +
        "'YYYY-mm-ddTHH:MM:SS' or 'YYYY-mm-ddTHH:MM:SSzzzzzz'")

try:
    if END == "None":
        end = datetime.datetime.now(datetime.timezone.utc)
    else:
        end = datetime.datetime.fromisoformat(END)
    if end.tzinfo is None:
        end = end.replace(tzinfo=datetime.timezone.utc)
except:
    sys.exit("Invalid end time. End time must be in isoformat: \n" +
        "'YYYY-mm-ddTHH:MM:SS' or 'YYYY-mm-ddTHH:MM:SSzzzzzz'")

try:
    if not os.path.isdir(WRITE_DIRECTORY):
        os.mkdir(WRITE_DIRECTORY)
except:
    sys.exit("Invalid directory path")


# ******************************* SET PATHS ****************************** #

PELICAN_300 = '../../underway_data/wh300_2.nc'
PELICAN_1200 = '../../underway_data/wh1200.nc'

# **************************** Make Sections ***************************** #

sections.ADCP_sections(PELICAN_300,WRITE_DIRECTORY,"Pelican_300",start,end,maxdepth=60)
sections.ADCP_sections(PELICAN_1200,WRITE_DIRECTORY,"Pelican_1200",start,end,maxdepth=15)
