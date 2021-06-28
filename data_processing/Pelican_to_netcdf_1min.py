import netCDF4
import numpy as np
import csv
import os
import datetime

NETCDF_FILE = r"/mnt/NAS/PE21_24_Shearman/data/met/2021 SUNRISE data/Pelican_FTMET_1min.nc"
MIDAS_DIRECTORY = "/home/pat/Dropbox/Pelican/MIDAS"#"/mnt/GOM/DATALOG40/EventData/MIDAS/"

variables = ["Heading", "Heading2", "Depth", "Temperature", "Salinity", "Conductivity", "SoundVelocity",
    "Transmission", "Fluorescence", "SPAR-Voltage", "SPAR-Microeinsteins", "BaroPressure", "AirTemp",
    "RelHumidity", "WindDirection", "WindSpeed", "AirTemp2", "BaroPressure2", "RelHumidity2",
    "WindDirection2", "WindSpeed2", "TWSpd-5sAvg", "ShortWaveRadiation", "LongWaveRadiation", "timeDerived"]
midas = {"Heading": "Sperry-MK1-Gyro-Hdg-deg",
    "Heading2": "Furuno-SC50-GPS-Hdg-Hdg",
    "Depth": "Knudsen-True-Depth-DRV-VALUE",
    "Temperature": "Thermosalinograph-Data-Temp",
    "Salinity": "Thermosalinograph-Data-Salinity",
    "Conductivity": "Thermosalinograph-Data-Conductivity",
    "SoundVelocity": "Thermosalinograph-Data-Sound-Velocity",
    "Transmission": "Transmissometer-percent-DRV-VALUE",
    "Fluorescence": "Wetstar-Flourometer-microgperL-DRV-VALUE",
    "SPAR-Voltage": "SPAR-Voltage-DRV-VALUE",
    "SPAR-Microeinsteins": "SPAR-Microeinsteins-DRV-VALUE",
    "AirTemp": "Air-Temp-1",
    "BaroPressure": "BaromPress-1",
    "RelHumidity": "Rel-Humidity-1",
    "WindDirection": "TrueWindDirection-1-DRV-DIRECTION",
    "WindSpeed": "TrueWindDirection-1-DRV-SPEED",
    "AirTemp2": "Air-Temp-2",
    "BaroPressure2": "BaromPress-2",
    "RelHumidity2": "Rel-Humidity-2",
    "WindDirection2": "True-Wind-2-DRV-DIRECTION",
    "WindSpeed2": "True-Wind-2-DRV-SPEED",
    "TWSpd-5sAvg": "TWSpd-5sAvg2-DRV-VALUE",
    "ShortWaveRadiation": "Radiometer-Feed--Short Wave Radiation from PSP in Watts Per M^2",
    "LongWaveRadiation": "Radiometer-Feed--Long Wave Radiation Watts Per Square Meter",
    "timeDerived": "time-DRV-VALUE"
    }
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
        last_minute = 0
    else:
        last_minute = rootgrp["time"][-1]
    # start_time = datetime.datetime(year=2019,month=1,day=1,tzinfo=datetime.timezone.utc) + datetime.timedelta(seconds=last_time)
    current_minute = 0
    minute_data = {"time": [],
        "Lon": [],
        "Lat": []}
    for var in variables:
        minute_data[var] = []

    for filename in files:
        with open(os.path.join(MIDAS_DIRECTORY,filename), newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                time = row["Time"]
                date = row["Date"]
                date = datetime.datetime.strptime(date,"%m/%d/%Y")
                time = datetime.time.fromisoformat(time)
                time = datetime.datetime.combine(date, time, tzinfo=datetime.timezone.utc)
                time_seconds = (time - datetime.datetime(year=2021,month=1,day=1,tzinfo=datetime.timezone.utc)).total_seconds()
                if time_seconds//60 > current_minute and time_seconds > last_minute:
                    for var in minute_data:
                        data[var].append(np.nanmean(minute_data[var]))
                        minute_data[var] = []
                    current_minute = time_seconds//60
                if time_seconds > last_minute:
                    lat = row["ADU800-GGA-Lat"]
                    minute_data["Lat"].append(float(lat[0:2]) + float(lat[2:-1])/60)
                    lon = row["ADU800-GGA-Lon"]
                    minute_data["Lon"].append(-1*float(lon[0:3]) - float(lon[3:-1])/60)
                    minute_data["time"].append((time_seconds//60)*60)
                    for var in variables:
                        value = row[midas[var]]
                        if not value:
                            value = "nan"
                        try:
                            minute_data[var].append(float(value))
                        except:
                            print("Error converting " + var + "to float")
                            minute_data[var].append(float("nan"))
    for key in minute_data:
        minute_data[key] = np.array(minute_data[key])
    tidx = minute_data["time"].size
    for key in minute_data:
        rootgrp[key][skip_old:skip_old+tidx] = minute_data[key]
except:
    raise
