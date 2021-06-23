import netCDF4
import numpy as np
import csv
import os
import datetime

NETCDF_FILE = "/home/pat/Dropbox/Pelican/MIDAS/Pelican_FTMET.nc"
MIDAS_DIRECTORY = "/mnt/GOM/DATALOG40/EventData/MIDAS/"

variables = ["Heading", "Depth", "Temperature", "Salinity", "Conductivity", "AirTemp", "BaroPressure",
    "RelHumidity", "WindDirection", "WindSpeed"]
midas = {"Heading": "Sperry-MK1-Gyro-Hdg-deg",
    "Depth": "Knudsen-True-Depth-DRV-VALUE",
    "Temperature": "Thermosalinograph-Data-Temp",
    "Salinity": "Thermosalinograph-Data-Salinity",
    "Conductivity": "Thermosalinograph-Data-Conductivity",
    "AirTemp": "Air-Temp-1",
    "BaroPressure": "BaromPress-1",
    "RelHumidity": "Rel-Humidity-1",
    "WindDirection": "TrueWindDirection-1-DRV-DIRECTION",
    "WindSpeed": "TrueWindDirection-1-DRV-SPEED"}
data = {"time": [],
    "Lon": [],
    "Lat": []}
for var in variables:
    data[var] = []
files = os.listdir(MIDAS_DIRECTORY)
files = [file for file in files if file[:6] == "MIDAS_" and file[-4:] == ".elg"]
files = sorted(files)

try:
    rootgrp = netCDF4.Dataset(NETCDF_FILE, "r+", format="NETCDF4")
    rootgrp.set_auto_mask(False)
    skip_old = rootgrp.dimensions["time"].size
    if skip_old == 0:
        last_time = 0
    else:
        last_time = rootgrp["time"][-1]
        print(last_time)
    start_time = datetime.datetime(year=2019,month=1,day=1,tzinfo=datetime.timezone.utc) + datetime.timedelta(seconds=last_time)


    for filename in files:
        with open(os.path.join(MIDAS_DIRECTORY,filename), newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                time = row["Time"]
                date = row["Date"]
                date = datetime.datetime.strptime(date,"%m/%d/%Y")
                time = datetime.time.fromisoformat(time)
                time = datetime.datetime.combine(date, time, tzinfo=datetime.timezone.utc)
                if time <= start_time:
                    continue
                lat = row["ADU800-GGA-Lat"]
                data["Lat"].append(float(lat[0:2]) + float(lat[2:-1])/60)
                lon = row["ADU800-GGA-Lon"]
                data["Lon"].append(-1*float(lon[0:3]) - float(lon[3:-1])/60)
                data["time"].append((time - datetime.datetime(year=2021,month=1,day=1,tzinfo=datetime.timezone.utc)).total_seconds())
                for var in variables:
                    value = row[midas[var]]
                    if not value:
                        value = "nan"
                    try:
                        data[var].append(float(value))
                    except:
                        print("Error converting " + var + "to float")
                        data[var].append(float("nan"))
    for key in data:
        data[key] = np.array(data[key])
    tidx = data["time"].size
    data["WindSpeed"] = data["WindSpeed"]*0.514444 # Convert from KNOTS to m/s
    for key in data:
        rootgrp[key][skip_old:skip_old+tidx] = data[key]
except:
    raise
