import netCDF4
import numpy as np
import csv
import os
from datetime import datetime

DIRECTORY = r"C:\Users\hildi\Documents\Stanford\Research\Sunrise\underway_data" #"/home/pat/Dropbox/Pelican/MIDAS"
WRITE_FILE = "./Pelican_FTMET.nc"

files = os.listdir(DIRECTORY)
files = [file for file in files if file[:6] == "MIDAS_" and file[-4:] == ".elg"]
files = sorted(files)
print(files)

try:
    rootgrp = netCDF4.Dataset(WRITE_FILE, "a", format="NETCDF4")
    print(rootgrp.dimensions)
except FileNotFoundError:
    rootgrp = netCDF4.Dataset(WRITE_FILE, "w", format="NETCDF4")
    timeDim = rootgrp.createDimension("time", None)
    time = rootgrp.createVariable("time","S1",("time",))
    time.units = "Isoformat String"
    lat = rootgrp.createVariable("Lat","f8",("time",))
    lat.units = "deg N"
    lon = rootgrp.createVariable("Lon","f8",("time",))
    lon.units = "deg E"
    heading = rootgrp.createVariable("Heading","f8",("time",))
    heading.units = "deg"
    depth = rootgrp.createVariable("Depth","f8",("time",))
    depth.units = "m"
    temperature = rootgrp.createVariable("Temperature","f8",("time",))
    temperature = "ITS-90, deg C"
    salinity = rootgrp.createVariable("Salinity","f8",("time",))
    salinity.units = "PSU"
    conductivity = rootgrp.createVariable("Conductivity","f8",("time",))
    conductivity.units = "mS/cm"
    airtemp = rootgrp.createVariable("AirTemp","f8",("time",))
    airtemp.units = "deg C"
    baropressure = rootgrp.createVariable("BaroPressure", "f8", ("time",))
    baropressure.units = "mBar"
    relhumidity = rootgrp.createVariable("RelHumidity", "f8", ("time",))
    relhumidity.units = "percentage"
    winddirection = rootgrp.createVariable("WindDirection","f8", ("time",))
    winddirection.units = "deg"
    windspeed = rootgrp.createVariable("WindSpeed","f8",("time",))
    windspeed.units = "m/s"
    
