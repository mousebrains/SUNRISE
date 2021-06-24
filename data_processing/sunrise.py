import netCDF4
import datetime
import gsw
import csv
import os
import numpy as np
import pandas as pd
import cmocean.cm as cmo
import cmocean
import matplotlib.pyplot as plt
import matplotlib.gridspec as gs
import matplotlib.units as munits
import matplotlib.dates as mdates
from matplotlib.ticker import AutoMinorLocator, MaxNLocator
from geopy.distance import distance
import kml_tools as kml
import re
import logging

CORIOLIS = 7*10**-5
PRESSURE = 0 # pressure [dbar] at throughflow
DEFAULT_LIMS = {"lower": False, "lowerLim": "0", "upper": False, "upperLim": "0"}

class ASV_DATAPOINT():

    def __init__(self,time):
        self.time = time
        self.lons = []
        self.lats = []
        self.temps = []
        self.sals = []
        self.u = []
        self.v = []
        self.w = []

    def get_lon(self):
        if self.lons:
            return np.nanmean(self.lons)
        else:
            return None

    def get_lat(self):
        if self.lats:
            return np.nanmean(self.lats)
        else:
            return None

    def get_temp(self):
        if self.temps:
            return np.nanmean(self.temps)
        else:
            return np.nan

    def get_sal(self):
        if self.sals:
            return np.nanmean(self.sals)
        else:
            return np.nan

def ADCP_section(filepath,start,end,directory,name,maxdepth=60,vmin=None,vmax=None,smin=None,smax=None):
    """Create ADCP section"""

    rootgrp = netCDF4.Dataset(filepath, "r")

    decimal_days = rootgrp["time"]
    yearbase = rootgrp.yearbase

    # Turn times into datetimes
    times = []
    base_time = datetime.datetime(yearbase,1,1,tzinfo=datetime.timezone.utc)
    for dd in decimal_days[:]:
        dt = datetime.timedelta(days=dd)
        times.append(base_time + dt)


    idx = np.zeros(len(times),dtype=bool)
    for i in range(len(times)):
        idx[i] = (times[i] >= start) and (times[i] <= end)

    times_use = [time for time, id in zip(times,idx) if id]
    if not times_use:
        # No data in time range
        return None
    timestamps = np.array([t.timestamp() for t in times_use])

    depths = rootgrp["depth"][0,:]
    idx2 = depths < maxdepth
    depths_use = depths[idx2]

    # Get data
    lon = rootgrp["lon"][idx]
    lat = rootgrp["lat"][idx]
    u = rootgrp["u"][idx,idx2]
    v = rootgrp["v"][idx,idx2]
    uship = rootgrp["uship"][idx]
    vship = rootgrp["vship"][idx]
    # heading = rootgrp["heading"][idx] # bearing in degrees clockwise

    # ship_speed = (uship**2 + vship**2)**0.5

    # deal with missing data points
    u[u > 10**30] = np.nan
    v[v > 10**30] = np.nan

    #shear
    ushear = -np.gradient(u,depths_use,axis=1)
    vshear = -np.gradient(v,depths_use,axis=1)
    # angle = np.angle(u+1j*v)

    # ******************** Get Limits *********************************** #
    vel_max = max(np.nanmax(u),np.nanmax(v),np.nanmax(-u),np.nanmax(-v))
    shear_max = max(np.nanmax(ushear), np.nanmax(vshear), np.nanmax(-ushear), np.nanmax(-vshear))
    if vmin is None:
        vmin = max(-1,-vel_max)
    if vmax is None:
        vmax = min(1,vel_max)
    if vmin > 0:
        vmin = 0
    if vmax < 0:
        vmax = 0
    if vmin == - vmax:
        vel_map = cmo.balance
    else:
        vel_map = cmocean.tools.crop(cmo.balance, vmin, vmax, 0)
    if smin is None:
        smin = -shear_max
    if smax is None:
        smax = shear_max
    if smin > 0:
        smin = 0
    if smax < 0:
        smax = 0
    if smin == - smax:
        shear_map = cmo.balance
    else:
        shear_map = cmocean.tools.crop(cmo.balance, smin, smax, 0)
    # ******************* Make Plots ************************************ #

    converter = mdates.ConciseDateConverter()
    munits.registry[datetime.datetime] = converter

    fig1 = plt.figure(figsize=(12, 6),constrained_layout=True)
    gs1 = gs.GridSpec(2, 2, figure=fig1, width_ratios=[1,1])

    axu=fig1.add_subplot(gs1[0,0])
    pu = axu.pcolor(times_use,depths_use,u.T,cmap=vel_map,shading='nearest',vmin=vmin, vmax=vmax)
    axu.xaxis_date()
    axu.invert_yaxis()
    axu.set_ylabel("Depth [m]")
    cb = plt.colorbar(pu,ax=axu)
    axu.set_title("$u$ [m/s]")

    axv=fig1.add_subplot(gs1[1,0])
    pv = axv.pcolor(times_use,depths_use,v.T,cmap=vel_map,shading='nearest',vmin=vmin, vmax=vmax)
    axv.xaxis_date()
    axv.invert_yaxis()
    axv.set_ylabel("Depth [m]")
    cb = plt.colorbar(pv,ax=axv)
    axv.set_title("$v$ [m/s]")


    axpos = fig1.add_subplot(gs1[:,1])
    axpos.plot(lon,lat,'k')
    npoints = len(times_use)
    skip = npoints//5
    lons = lon[::skip]
    lats = lat[::skip]
    tim = times_use[::skip]
    cols = ["k", "g", "r", "b", "m"]
    markers = ["o","^", "s", "p", "h"]
    for i in range(5):
        axpos.plot(lon[(i)*skip:(i+1)*skip + 1],lat[(i)*skip:(i+1)*skip + 1],color=cols[i])
        axpos.plot(lons[i],lats[i],color=cols[i],marker=markers[i],linestyle="None",label=tim[i].strftime("%d %b\n%H:%M"))
    axpos.xaxis.set_major_locator(MaxNLocator(nbins=5, steps=[1,2,5,10]))
    axpos.set_xlabel("Longitude [$^\circ$E]")
    axpos.set_ylabel("Latitude [$^\circ$N]")
    axpos.set_title("Ship Track")
    axpos.legend(bbox_to_anchor=(1, 1), loc='upper left')
    # axpos.legend()
    # axpmv = fig1.add_subplot(gs1[1,1])
    # ppmv = axpmv.pcolor(times_use,depths_use,pm_vorticity.T,cmap=cmo.balance,shading="nearest",vmin=-pmv_max,vmax=pmv_max)
    # axpmv.xaxis_date()
    # axpmv.invert_yaxis()
    # axpmv.set_ylabel("Depth [m]")
    # cb = plt.colorbar(ppmv,ax=axpmv)
    # axpmv.set_title("Poor Man's Vorticity [$f$]")

    fig1.suptitle(name + ": " + start.strftime("%d-%b %H:%M") + " - " + end.strftime("%d-%b %H:%M"))
    fig1.savefig(os.path.join(directory,name + "_velocity.png"))

    fig2 = plt.figure(figsize=(12, 6),constrained_layout=True)
    gs2 = gs.GridSpec(2, 2, figure=fig2, width_ratios=[1,1])

    axuz = fig2.add_subplot(gs2[0,:])
    puz = axuz.pcolor(times_use,depths_use,ushear.T,cmap=shear_map,shading="nearest",vmin=smin,vmax=smax)
    axuz.xaxis_date()
    axuz.invert_yaxis()
    axuz.set_ylabel("Depth [m]")
    cb = plt.colorbar(puz,ax=axuz)
    axuz.set_title("$u_z$ [1/s]")

    axvz = fig2.add_subplot(gs2[1,:])
    pvz = axvz.pcolor(times_use,depths_use,vshear.T,cmap=shear_map,shading="nearest",vmin=smin,vmax=smax)
    axvz.xaxis_date()
    axvz.invert_yaxis()
    axvz.set_ylabel("Depth [m]")
    cb = plt.colorbar(pvz,ax=axvz)
    axvz.set_title("$v_z$ [1/s]")



    # axtmp = fig2.add_subplot(gs2[1,:])
    # axtmp.plot(times_use,heading/180,label="heading")
    # axtmp.plot(times_use,uship,label="uship")
    # axtmp.plot(times_use,vship,label="vship")
    # axtmp.set_xlim(times_use[0],times_use[-1])
    # axtmp.legend()
    # axang = fig2.add_subplot(gs2[1,1])
    # pang = axang.pcolor(times_use,depths_use,angle.T,cmap=cmo.phase,shading="nearest",vmin=-np.pi,vmax=np.pi)
    # axang.xaxis_date()
    # axang.invert_yaxis()
    # axang.set_ylabel("Depth [m]")
    # cb = plt.colorbar(pang,ax=axang)
    # axang.set_title("$Shear Angle$ [$^r$]")

    fig2.suptitle(name + ": " + start.strftime("%d-%b %H:%M") + " - " + end.strftime("%d-%b %H:%M"))
    fig2.savefig(os.path.join(directory,name + "_shear.png"))

def get_sigma0(sal,temp,lon,lat):
    SA = gsw.SA_from_SP(sal,PRESSURE,lon,lat)
    CT = gsw.CT_from_t(SA,temp,PRESSURE)
    return gsw.density.sigma0(SA,CT)

def parse_WSFT(filename, start, end, skip=1, hdrFix = True):
    df = pd.DataFrame()
    with open(filename, "r") as fp:
        info = {}
        hdr = None
        seen = set()
        cnt = 0
        for line in fp:
            cnt += 1
            line = line.strip() # Strip off whitespace
            fields = line.split("\t") # Split by tabs
            fields = list(map(lambda x: x.strip(), fields))
            if cnt <= skip: # Before header line
                for field in fields:
                    (key, val) = field.split(":")
                    info[key.strip()] = val.strip()
                # for key in sorted(info):
                #     print("INFO:", key, "->", info[key])
                continue
            if hdr is None:
                hdr = []
                for item in fields:
                    if len(item):
                        if hdrFix:
                            if item == "POSMV Lat":
                                hdr.append("MAYBE TEMP?")
                            elif item == "RM Young Barometer mbStbd RM Young Winds Rel. Wind Spd. Knots":
                                hdr.append("RM Young Barometer mb")
                                item = "Stbd RM Young Winds Rel. Wind Spd. Knots"
                        while item in seen: item += "X"
                        seen.add(item)
                        hdr.append(item)
                    else: # Empty item
                        if not hdrFix or len(hdr) not in [58]:
                            item = "Empty"
                            while item in seen: item += "X"
                            seen.add(item)
                            hdr.append(item)
                continue
            item = pd.Series(fields, index=hdr[:len(fields)])
            df = df.append(item, ignore_index=True)

        # save data
        latitudes = []
        longitudes = []
        times = []
        salinities = []
        temperatures = []

        for i in range(len(df['Time'])):

            newtime=datetime.datetime.strptime(df['Date'][i] + df['Time'][i], "%d %B%Y %H:%M:%S").\
                        replace(tzinfo=datetime.timezone.utc)

            if (newtime >= start) and (newtime <= end):
                longitudes.append(-float(df["Lon Dec. Deg.XX"][i].split()[-1]))
                latitudes.append(float(df["Lat Dec. Deg.XX"][i].split()[-1]))
                temperatures.append(float(df["MicroTSG1MicroTSG Temperature Degrees C"][i]))
                salinities.append(float(df['MicroTSG Salinity PSU'][i]))
                times.append(newtime)

        sigmas = [get_sigma0(s,t,lo,la) for s,t,lo,la in zip(salinities,temperatures,longitudes,latitudes)]

        # Calc salt grad
        if latitudes:
            seg_distance = np.zeros(len(latitudes)-1)
            for i in range(seg_distance.size):
                seg_distance[i] = distance((latitudes[i+1],longitudes[i+1]),(latitudes[i],longitudes[i])).km
            distances = np.zeros(len(latitudes))
            distances[1:] = np.cumsum(seg_distance)
            salt_grad = np.abs(np.gradient(np.asarray(salinities),distances))
        else:
            salt_grad = []

        return {"longitudes": longitudes,
            "latitudes": latitudes,
            "times": times,
            "salinities": salinities,
            "temperatures": temperatures,
            "sigmas": sigmas,
            "sal_grad": salt_grad}

def parse_PFT(filenames, start, end):

    Pelican_latitudes = []
    Pelican_longitudes = []
    Pelican_times = []
    Pelican_salinities = []
    Pelican_temperatures = []
    Pelican_sigmas = []

    for filename in filenames:
        with open(filename, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                time = row["Time"]
                if time[-2:] != "00":
                    continue
                date = row["Date"]
                date = datetime.datetime.strptime(date,"%m/%d/%Y")
                time = datetime.time.fromisoformat(time)
                time = datetime.datetime.combine(date, time, tzinfo=datetime.timezone.utc)
                if time > end:
                    break
                if time < start:
                    continue

                lat = row["ADU800-GGA-Lat"]
                Pelican_latitudes.append(float(lat[0:2]) + float(lat[2:-1])/60)
                lon = row["ADU800-GGA-Lon"]
                Pelican_longitudes.append(-1*float(lon[0:3]) - float(lon[3:-1])/60)

                Pelican_times.append(time)

                # Pelican temperature
                temp = row["Thermosalinograph-Data-Temp"]
                if not temp:
                    # Handle empty temperature field
                    temp = "nan"
                try:
                    Pelican_temperatures.append(float(temp))
                except:
                    print("Unexpected Temperature Value")
                    Pelican_temperatures.append(float("nan"))

                # Pelican Salinity
                sal = row["Thermosalinograph-Data-Salinity"]
                if not sal:
                    # Handle empty salinity field
                    sal = "nan"
                try:
                    Pelican_salinities.append(float(sal))
                except:
                    print("Unexpected Salinity Value")
                    Pelican_salinities.append(float("nan"))

                # Pelican potential density
                try:
                    sigma0 = get_sigma0(float(sal), float(temp),
                        Pelican_longitudes[-1], Pelican_latitudes[-1])
                except:
                    sigma0 = float("nan")
                Pelican_sigmas.append(sigma0)

        # Calc salt grad
    if Pelican_latitudes:
        seg_distance = np.zeros(len(Pelican_latitudes)-1)
        for i in range(seg_distance.size):
            seg_distance[i] = distance((Pelican_latitudes[i+1],Pelican_longitudes[i+1]),(Pelican_latitudes[i],Pelican_longitudes[i])).km
        distances = np.zeros(len(Pelican_latitudes))
        distances[1:] = np.cumsum(seg_distance)
        Pelican_salt_grad = np.abs(np.gradient(np.asarray(Pelican_salinities),distances))
    else:
        Pelican_salt_grad = []

    return {"latitudes": Pelican_latitudes,
        "longitudes": Pelican_longitudes,
        "times": Pelican_times,
        "salinities": Pelican_salinities,
        "temperatures": Pelican_temperatures,
        "sigmas": Pelican_sigmas,
        "sal_grad": Pelican_salt_grad}

def parse_ASV(filename, start, end):

    latitudes = []
    longitudes = []
    times = []
    salinities = []
    temperatures = []
    sigmas = []
    ADCP_u = []
    ADCP_v = []
    ADCP_w = []

    fltRE = r"[+-]?\d+[.]?\d*"
    regexp = re.compile(r"\s*(\d{2}-\w+-\d{4}\s+\d{2}:\d{2}:\d{2})\s*(\w+)\s*--\s*(\w+)\s*--\s*(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})\s*UTC\s*--\s*(.*)\s*")
    reADCP = re.compile(r"ADATE\s*(\d+)\s*ATIME\s*(\d+)\s+" \
            r"u\s*(" + fltRE + r")\s*" \
            r"v\s*(" + fltRE + r")\s*" \
            r"w\s*(" + fltRE + r")\s*")
    reNAVINFO = re.compile(r"LAT\s*(" + fltRE + ")\s*LON\s*(" + fltRE + ")")
    reKeel = re.compile(r"KDATE\s*\d+-\d+-\d+\s*KTIME\s*\d+:\d+:\d+[.]\d*\s*" \
            + r"Temp\s*(" + fltRE + r")\s*" \
            + r"Sal\s*(" + fltRE + r")\s*")


    datapoints = {}
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            matches = regexp.match(line)
            if not matches:
                # print("Malformed line:", line if len(line) < 100 else line[:100])
                continue
            received = matches[1]
            unitName = matches[2]
            identifier = matches[3]
            timestring = matches[4]
            data = matches[5]
            try:
                time = datetime.datetime.strptime(timestring, "%Y/%m/%d %H:%M:%S") \
                        .replace(second=0, tzinfo=datetime.timezone.utc)
                if time < start or time > end:
                    continue
                timestring = time.isoformat()
                if timestring not in datapoints:
                    datapoints[timestring] = ASV_DATAPOINT(time)

                if identifier == "navinfo":
                    matches = reNAVINFO.match(data)
                    if not matches:
                        # print("Malformed NAVINFO line:", line)
                        continue
                    lat = float(matches[1])
                    lon = float(matches[2])
                    if (lat != 0) and (abs(lat) <= 90) and (lon != 0) and (abs(lon) < 180):
                        datapoints[timestring].lats.append(lat)
                        datapoints[timestring].lons.append(lon)
                elif identifier == "keelctd":
                    matches = reKeel.match(data)
                    if not matches:
                        # print("Malformed KEELCTD line:", line)
                        continue
                    temp = float(matches[1])
                    salt = float(matches[2])
                    if (temp > 0) and (temp < 40) and (salt > 10) and (salt < 40):
                        datapoints[timestring].temps.append(temp)
                        datapoints[timestring].sals.append(salt)
                elif identifier == "adcp":
                    matches = reADCP.match(data)
                    if not matches:
                        # print("Malformed ADCP line:", line)
                        continue
                    adate = matches[1]
                    atime = matches[2]
                    u = matches[3]
                    v = matches[4]
                    w = matches[5]
                    datapoints[timestring].u.append(u)
                    datapoints[timestring].v.append(v)
                    datapoints[timestring].w.append(w)
                # else:
                    # print(f"Unsupport type '{identifier}' in {line}")
            except Exception as e:
                logging.exception("ERROR processing line %s", line)

        timestrings = datapoints.keys()
        sorted_keys = sorted(timestrings)
        for key in sorted_keys:
            data = datapoints[key]
            lon = data.get_lon()
            lat = data.get_lat()
            if lon is not None and lat is not None:
                temp = data.get_temp()
                sal = data.get_sal()
                sigma = get_sigma0(sal,temp,lon,lat)
                times.append(data.time)
                latitudes.append(lat)
                longitudes.append(lon)
                salinities.append(sal)
                temperatures.append(temp)
                sigmas.append(sigma)

    # Calc salt grad
    if latitudes:
        seg_distance = np.zeros(len(latitudes)-1)
        for i in range(seg_distance.size):
            seg_distance[i] = distance((latitudes[i+1],longitudes[i+1]),(latitudes[i],longitudes[i])).km
        distances = np.zeros(len(latitudes))
        distances[1:] = np.cumsum(seg_distance)
        salt_grad = np.abs(np.gradient(np.asarray(salinities),distances))
    else:
        salt_grad = []

    return {"longitudes": longitudes,
        "latitudes": latitudes,
        "times": times,
        "salinities": salinities,
        "temperatures": temperatures,
        "sigmas": sigmas,
        "sal_grad": salt_grad}

def throughflow(P_FT, WS_FT, start,end,directory,sal_kmz=True,temp_kmz=True,density_kmz=True,salg_kmz=True,sal_png=True,temp_png=True,density_png=True,salg_png=True,sal_lims=DEFAULT_LIMS,temp_lims=DEFAULT_LIMS,density_lims=DEFAULT_LIMS):
    """Get throughflow data from Pelican, WS, and ASVs (ASV not yet implemented) and create kmz/pngs"""
    # ******************************* PELICAN ********************************* #

    Pelican_latitudes = list(P_FT["latitudes"])
    Pelican_longitudes = list(P_FT["longitudes"])
    Pelican_times = list(P_FT["times"])
    Pelican_salinities = list(P_FT["salinities"])
    Pelican_temperatures = list(P_FT["temperatures"])
    Pelican_sigmas = list(P_FT["sigmas"])
    Pelican_sal_grads = list(P_FT["sal_grad"])

    # *************************** WALTON SMITH ******************************** #

    WS_longitudes = list(WS_FT["longitudes"])
    WS_latitudes = list(WS_FT["latitudes"])
    WS_times = list(WS_FT["times"])
    WS_salinities = list(WS_FT["salinities"])
    WS_temperatures = list(WS_FT["temperatures"])
    WS_sigmas = list(WS_FT["sigmas"])
    WS_sal_grads = list(WS_FT["sal_grad"])

    Pelican_data = {
        "Salinity": Pelican_salinities,
        "Temperature": Pelican_temperatures,
        "Potential Density": Pelican_sigmas,
        "Salinity Gradient": Pelican_sal_grads
    }

    WS_data = {
        "Salinity": WS_salinities,
        "Temperature": WS_temperatures,
        "Potential Density": WS_sigmas,
        "Salinity Gradient": WS_sal_grads
    }
    # *************************** CREATE KMZ/PNG *************************** #

    if sal_kmz or sal_png:
        if not sal_lims["lower"]:
            try:
                sal_min_P = 32
            except ValueError: # empty list
                sal_min_P = 100
            try:
                sal_min_WS = 32
            except ValueError: # empty list
                sal_min_WS = 100
            sal_min = min(sal_min_P, sal_min_WS)
        else:
            sal_min = float(sal_lims["lowerLim"])
        if not sal_lims["upper"]:
            try:
                sal_max_P = 36
            except ValueError: # empty list
                sal_max_P = 0
            try:
                sal_max_WS = 36
            except ValueError: # empty list
                sal_max_WS = 0
            sal_max = max(sal_max_P, sal_max_WS)
        else:
            sal_max = float(sal_lims["upperLim"])

    if sal_kmz:
        kml.kml_coloured_line(directory,
            "Pelican_Salinity",
            Pelican_data,
            "Salinity",
            Pelican_longitudes,
            Pelican_latitudes,
            Pelican_times,
            cmo.deep,
            "Pelican Salinity",
            dmax=sal_max,
            dmin=sal_min)

        kml.kml_coloured_line(directory,
            "Walton_Smith_Salinity",
            WS_data,
            "Salinity",
            WS_longitudes,
            WS_latitudes,
            WS_times,
            cmo.deep,
            "Walton Smith Salinity",
            dmax=sal_max,
            dmin=sal_min)
    if sal_png:
        fig, ax = plt.subplots(figsize=(12,9))
        sc = ax.scatter(Pelican_longitudes + WS_longitudes,
            Pelican_latitudes + WS_latitudes,
            c=(Pelican_salinities + WS_salinities),
            vmin=sal_min,
            vmax=sal_max,
            cmap=cmo.deep)
        if Pelican_times:
            ax.annotate("P",(Pelican_longitudes[-1], Pelican_latitudes[-1]),
                textcoords="offset pixels", xytext=(5, 0), size=20)
        if WS_times:
            ax.annotate("WS",(WS_longitudes[-1], WS_latitudes[-1]),
                textcoords="offset pixels", xytext=(5, 0), size=20)
        ax.set_xlabel("Longitude [$^\circ$E]")
        ax.set_ylabel("Latitude [$^\circ$N]")
        cb = fig.colorbar(sc)
        ax.set_title("Through Flow Salinity " +
            start.strftime("%d-%b %H:%M") + " - " +
            end.strftime("%d-%b %H:%M"))
        fig.savefig(os.path.join(directory,"Salinity.png"))

    if temp_kmz or temp_png:
        if not temp_lims["lower"]:
            try:
                temp_min_P = np.nanmin(Pelican_temperatures)
            except ValueError: # empty list
                temp_min_P = 100
            try:
                temp_min_WS = np.nanmin(WS_temperatures)
            except ValueError: # empty list
                temp_min_WS = 100
            temp_min = min(temp_min_P, temp_min_WS)
        else:
            temp_min = float(temp_lims["lowerLim"])
        if not temp_lims["upper"]:
            try:
                temp_max_P = np.nanmax(Pelican_temperatures)
            except ValueError: # empty list
                temp_max_P = 0
            try:
                temp_max_WS = np.nanmax(WS_temperatures)
            except ValueError: # empty list
                temp_max_WS = 0
            temp_max = max(temp_max_P, temp_max_WS)
        else:
            temp_max = float(temp_lims["upperLim"])

    if temp_kmz:
        kml.kml_coloured_line(directory,
            "Pelican_Temperature",
            Pelican_data,
            "Temperature",
            Pelican_longitudes,
            Pelican_latitudes,
            Pelican_times,
            cmo.thermal,
            "Pelican Temperature",
            dmax=temp_max,
            dmin=temp_min)

        kml.kml_coloured_line(directory,
            "Walton_Smith_Temperature",
            WS_data,
            "Temperature",
            WS_longitudes,
            WS_latitudes,
            WS_times,
            cmo.thermal,
            "Walton Smith Temperature",
            dmax=temp_max,
            dmin=temp_min)
    if temp_png:
        fig, ax = plt.subplots(figsize=(12,9))
        sc = ax.scatter(Pelican_longitudes + WS_longitudes,
            Pelican_latitudes + WS_latitudes,
            c=(Pelican_temperatures + WS_temperatures),
            vmin=temp_min,
            vmax=temp_max,
            cmap=cmo.thermal)
        if Pelican_times:
            ax.annotate("P",(Pelican_longitudes[-1], Pelican_latitudes[-1]),
                textcoords="offset pixels", xytext=(5, 0), size=20)
        if WS_times:
            ax.annotate("WS",(WS_longitudes[-1], WS_latitudes[-1]),
                textcoords="offset pixels", xytext=(5, 0), size=20)
        ax.set_xlabel("Longitude [$^\circ$E]")
        ax.set_ylabel("Latitude [$^\circ$N]")
        cb = fig.colorbar(sc)
        ax.set_title("Through Flow Temperature " +
            start.strftime("%d-%b %H:%M") + " - " +
            end.strftime("%d-%b %H:%M"))
        fig.savefig(os.path.join(directory,"Temperature.png"))

    if density_kmz or density_png:
        if not density_lims["lower"]:
            try:
                sigma_min_P = np.nanmin(Pelican_sigmas)
            except ValueError: # empty list
                sigma_min_P = 100
            try:
                sigma_min_WS = np.nanmin(WS_sigmas)
            except ValueError: # empty list
                sigma_min_WS = 100
            sigma_min = min(sigma_min_P, sigma_min_WS)
        else:
            sigma_min = float(density_lims["lowerLim"])
        if not density_lims["upper"]:
            try:
                sigma_max_P = np.nanmax(Pelican_sigmas)
            except ValueError: # empty list
                sigma_max_P = 0
            try:
                sigma_max_WS = np.nanmax(WS_sigmas)
            except ValueError: # empty list
                sigma_max_WS = 0
            sigma_max = max(sigma_max_P, sigma_max_WS)
        else:
            sigma_max = float(density_lims["upperLim"])

    if density_kmz:
        kml.kml_coloured_line(directory,
            "Pelican_Density",
            Pelican_data,
            "Potential Density",
            Pelican_longitudes,
            Pelican_latitudes,
            Pelican_times,
            cmo.dense,
            "Pelican Density",
            dmax=sigma_max,
            dmin=sigma_min)

        kml.kml_coloured_line(directory,
            "Walton_Smith_Density",
            WS_data,
            "Potential Density",
            WS_longitudes,
            WS_latitudes,
            WS_times,
            cmo.dense,
            "Walton Smith Density",
            dmax=sigma_max,
            dmin=sigma_min)
    if density_png:
        fig, ax = plt.subplots(figsize=(12,9))
        sc = ax.scatter(Pelican_longitudes + WS_longitudes,
            Pelican_latitudes + WS_latitudes,
            c=(Pelican_sigmas + WS_sigmas),
            vmin=sigma_min,
            vmax=sigma_max,
            cmap=cmo.dense)
        if Pelican_times:
            ax.annotate("P",(Pelican_longitudes[-1], Pelican_latitudes[-1]),
                textcoords="offset pixels", xytext=(5, 0), size=20)
        if WS_times:
            ax.annotate("WS",(WS_longitudes[-1], WS_latitudes[-1]),
                textcoords="offset pixels", xytext=(5, 0), size=20)
        ax.set_xlabel("Longitude [$^\circ$E]")
        ax.set_ylabel("Latitude [$^\circ$N]")
        cb = fig.colorbar(sc)
        ax.set_title("Through Flow Potential Density " +
            start.strftime("%d-%b %H:%M") + " - " +
            end.strftime("%d-%b %H:%M"))
        fig.savefig(os.path.join(directory,"Density.png"))

    if salg_kmz:
        kml.kml_coloured_line(directory,
            "Pelican_Salinity_Gradient",
            Pelican_data,
            "Salinity Gradient",
            Pelican_longitudes,
            Pelican_latitudes,
            Pelican_times,
            cmo.matter,
            "Pelican Salinity Gradient")

        kml.kml_coloured_line(directory,
            "Walton_Smith_Salinity_Gradient",
            WS_data,
            "Salinity Gradient",
            WS_longitudes,
            WS_latitudes,
            WS_times,
            cmo.matter,
            "Walton Smith Salinity Gradient")
    if salg_png:
        fig, ax = plt.subplots(figsize=(12,9))
        sc = ax.scatter(Pelican_longitudes + WS_longitudes,
            Pelican_latitudes + WS_latitudes,
            c=(Pelican_sal_grads + WS_sal_grads),
            cmap=cmo.matter)
        if Pelican_times:
            ax.annotate("P",(Pelican_longitudes[-1], Pelican_latitudes[-1]),
                textcoords="offset pixels", xytext=(5, 0), size=20)
        if WS_times:
            ax.annotate("WS",(WS_longitudes[-1], WS_latitudes[-1]),
                textcoords="offset pixels", xytext=(5, 0), size=20)
        ax.set_xlabel("Longitude [$^\circ$E]")
        ax.set_ylabel("Latitude [$^\circ$N]")
        cb = fig.colorbar(sc)
        ax.set_title("Through Flow Salinity Gradient " +
            start.strftime("%d-%b %H:%M") + " - " +
            end.strftime("%d-%b %H:%M"))
        fig.savefig(os.path.join(directory,"Salinity_Gradient.png"))

    return

def ADCP_PMV(DATAPATH,start,end,directory,AvgDepth=5,dmax_PMV=1,dmin_PMV=-1,pmv_filename="ADCP_PMV",label="Vort/f",kmz=True):
    """Get Poor Man's Vorticity from an ADCP file and create a kmz"""

    # Load data
    rootgrp = netCDF4.Dataset(DATAPATH, "r", format="NETCDF4")

    # Select times
    decimal_days = rootgrp["time"]
    yearbase = rootgrp.yearbase
    times = []
    base_time = datetime.datetime(yearbase,1,1,tzinfo=datetime.timezone.utc)
    # Turn times into datetimes
    for dd in decimal_days[:]:
        dt = datetime.timedelta(days=dd)
        times.append(base_time + dt)
    # Select
    idx = np.zeros(len(times),dtype=bool)
    for i in range(len(times)):
        idx[i] = (times[i] >= start) and (times[i] <= end)

    if not idx.any():
        return None

    # Select depths
    depth = rootgrp["depth"][0,:]
    idx_dep = np.where((depth-depth[0])<=AvgDepth)[0]

    # Get data
    lon = rootgrp["lon"][idx]
    lat = rootgrp["lat"][idx]
    u = rootgrp["u"][idx,idx_dep]
    v = rootgrp["v"][idx,idx_dep]
    uship = rootgrp["uship"][idx]
    vship = rootgrp["vship"][idx]
    heading = rootgrp["heading"][idx] # bearing in degrees clockwise
    ship_speed = (uship**2 + vship**2)**0.5
    times_filtered = [time for time, id in zip(times,idx) if id]

    # CORIOLIS
    CORIOLIS = 2. * (2.*np.pi/86400.) * np.sin(np.mean(lat)/180.*np.pi)

    # calculate distances
    seg_distance = np.zeros(lat.size-1)
    for i in range(seg_distance.size):
        seg_distance[i] = distance((lat[i+1],lon[i+1]),(lat[i],lon[i])).km*1000.
    distances = np.zeros_like(lat)
    distances[1:] = np.cumsum(seg_distance)

    # calc ship perpendicular velocity
    heading_grad = np.abs(np.gradient(np.sin(heading*np.pi/180),distances)) \
                    + np.abs(np.gradient(np.cos(heading*np.pi/180),distances))
    heading_change = heading_grad > 0.01
    spv = v*np.sin(heading[:,None]*np.pi/180) - u*np.cos(heading[:,None]*np.pi/180)
    spv[heading_change,:] = np.nan
    spv[ship_speed<1] = np.nan


    # Calc PMV
    pm_vorticity = np.gradient(spv,distances,axis=0)/CORIOLIS
    pm_vorticity[heading_change,:] = np.nan
    pm_vorticity[ship_speed<1] = np.nan
    pm_vorticity = np.mean(pm_vorticity, axis=-1)

    # Create KMZ
    if kmz:
        kml.kml_coloured_line(directory,
            pmv_filename,
            {"PM Vorticity": pm_vorticity},
            "PM Vorticity",
            lon,
            lat,
            times_filtered,
            cmo.curl,
            label,
            dmin=dmin_PMV,
            dmax=dmax_PMV)

    out_dict = {
        "longitudes": lon,
        "latitudes": lat,
        "times": times,
        "pm_vorticity": pm_vorticity,
        "label": label
    }

    return out_dict

def PMV_png(start,end,directory,*args,dmin_PMV=-1, dmax_PMV=1):
    fig, ax = plt.subplots(figsize=(12,9))
    for pmv in args:
        if pmv is not None:
            sc =ax.scatter(pmv["longitudes"],pmv["latitudes"],c=pmv["pm_vorticity"],cmap=cmo.curl,vmin=dmin_PMV,vmax=dmax_PMV)
            ax.plot(pmv["longitudes"][-1],pmv["latitudes"][-1],marker="p",linestyle="None",label=pmv["label"])
    ax.set_xlabel("Longitude [$^\circ$E]")
    ax.set_ylabel("Latitude [$^\circ$N]")
    ax.legend()
    cb = fig.colorbar(sc)
    ax.set_title("Poor Man's Vorticity [f] " + start.strftime("%d-%b %H:%M") + " - " +
    end.strftime("%d-%b %H:%M"))
    fig.savefig(os.path.join(directory,"Poor_Mans_Vorticity.png"))

def ShipSurface_png(P_FT, WS_FT,ADCP_PL,ADCP_WS,start,end,directory,plot_P=True,plot_WS=True,sal_lims=DEFAULT_LIMS,temp_lims=DEFAULT_LIMS,density_lims=DEFAULT_LIMS,PM_lims=(-1,1)):
    # Set temp limits
    if not temp_lims["lower"]:
        try:
            temp_min_P = np.nanmin(P_FT["temperatures"])
        except ValueError: # empty list
            temp_min_P = 100
        try:
            temp_min_WS = np.nanmin(WS_FT["temperatures"])
        except ValueError: # empty list
            temp_min_WS = 100
    else:
        temp_min_P = float(temp_lims["lowerLim"])
        temp_min_WS = float(temp_lims["lowerLim"])
    if not temp_lims["upper"]:
        try:
            temp_max_P = np.nanmax(P_FT["temperatures"])
        except ValueError: # empty list
            temp_max_P = 0
        try:
            temp_max_WS = np.nanmax(WS_FT["temperatures"])
        except ValueError: # empty list
            temp_max_WS = 0
    else:
        temp_max_P = float(temp_lims["upperLim"])
        temp_max_WS = float(temp_lims["upperLim"])
    # Set salt limits
    if not sal_lims["lower"]:
        try:
            sal_min_P = np.nanmin(P_FT["salinities"])
        except ValueError: # empty list
            sal_min_P = 100
        try:
            sal_min_WS = np.nanmin(WS_FT["salinities"])
        except ValueError: # empty list
            sal_min_WS = 100
    else:
        sal_min_P = float(sal_lims["lowerLim"])
        sal_min_WS = float(sal_lims["lowerLim"])
    if not sal_lims["upper"]:
        try:
            sal_max_P = np.nanmax(P_FT["salinities"])
        except ValueError: # empty list
            sal_max_P = 0
        try:
            sal_max_WS = np.nanmax(WS_FT["salinities"])
        except ValueError: # empty list
            sal_max_WS = 0
    else:
        sal_max_P = float(sal_lims["upperLim"])
        sal_max_WS = float(sal_lims["upperLim"])

    if not density_lims["lower"]:
        try:
            sigma_min_P = np.nanmin(P_FT["sigmas"])
        except ValueError: # empty list
            sigma_min_P = 100
        try:
            sigma_min_WS = np.nanmin(WS_FT["sigmas"])
        except ValueError: # empty list
            sigma_min_WS = 100
    else:
        sigma_min_P = float(density_lims["lowerLim"])
        sigma_min_WS = float(density_lims["lowerLim"])
    if not density_lims["upper"]:
        try:
            sigma_max_P = np.nanmax(P_FT["sigmas"])
        except ValueError: # empty list
            sigma_max_P = 0
        try:
            sigma_max_WS = np.nanmax(WS_FT["sigmas"])
        except ValueError: # empty list
            sigma_max_WS = 0
    else:
        sigma_max_P = float(density_lims["upperLim"])
        sigma_max_WS = float(density_lims["upperLim"])
    # Pelican
    if plot_P & (P_FT is not None) & (ADCP_PL is not None):
        fig, axs = plt.subplots(2, 2, figsize=(12, 9))
        fig.subplots_adjust(left=0.02, bottom=0.06, right=0.95, top=0.94)
        pms = axs[0,0].scatter(P_FT['longitudes'][:], P_FT['latitudes'][:],\
                  c=P_FT['salinities'], \
                   vmax=sal_max_P, vmin=sal_min_P, cmap=cmo.haline)
        axs[0,0].set_xlabel("Longitude [$^\circ$E]")
        axs[0,0].set_ylabel("Latitude [$^\circ$N]")
        axs[0,0].set_title("Salinity")
        pmt = axs[0,1].scatter(P_FT['longitudes'][:], P_FT['latitudes'][:],\
                  c=P_FT['temperatures'], \
                   vmax=temp_max_P, vmin=temp_min_P, cmap=cmo.thermal)
        axs[0,1].set_xlabel("Longitude [$^\circ$E]")
        axs[0,1].set_ylabel("Latitude [$^\circ$N]")
        axs[0,1].set_title("Temperature")
        pmd = axs[1,0].scatter(P_FT['longitudes'][:], P_FT['latitudes'][:],\
                  c=P_FT['sigmas'], \
                  vmax=sigma_max_P, vmin=sigma_min_P,cmap=cmo.dense)
        axs[1,0].set_xlabel("Longitude [$^\circ$E]")
        axs[1,0].set_ylabel("Latitude [$^\circ$N]")
        axs[1,0].set_title("Potential Density")
        pmp = axs[1,1].scatter(ADCP_PL['longitudes'][:], ADCP_PL['latitudes'][:],\
                  c=ADCP_PL['pm_vorticity'], \
                  vmax=PM_lims[-1],vmin=PM_lims[0],cmap=cmo.curl)
        axs[1,1].set_xlabel("Longitude [$^\circ$E]")
        axs[1,1].set_ylabel("Latitude [$^\circ$N]")
        axs[1,1].set_title("Poor Man's Vorticity [f]")
        fig.colorbar(pms, ax=axs[0,0])
        fig.colorbar(pmt, ax=axs[0,1])
        fig.colorbar(pmd, ax=axs[1,0])
        fig.colorbar(pmp, ax=axs[1,1])
        fig.suptitle("Pelican Surface Data" + ": " + start.strftime("%d-%b %H:%M") + " - " + end.strftime("%d-%b %H:%M"))
        fig.tight_layout()
        fig.savefig(os.path.join(directory,"Pelican_Surface_panels.png"),dpi=100)
        plt.close(fig)
    # WS
    if plot_WS & (WS_FT is not None) & (ADCP_WS is not None):
        fig, axs = plt.subplots(2, 2, figsize=(12, 9))
        fig.subplots_adjust(left=0.02, bottom=0.06, right=0.95, top=0.94)
        pms = axs[0,0].scatter(WS_FT['longitudes'][:], WS_FT['latitudes'][:],\
                  c=WS_FT['salinities'], \
                   vmax=sal_max_WS, vmin=sal_min_WS, cmap=cmo.haline)
        axs[0,0].set_xlabel("Longitude [$^\circ$E]")
        axs[0,0].set_ylabel("Latitude [$^\circ$N]")
        axs[0,0].set_title("Salinity")
        pmt = axs[0,1].scatter(WS_FT['longitudes'][:], WS_FT['latitudes'][:],\
                  c=WS_FT['temperatures'], \
                   vmax=temp_max_WS, vmin=temp_min_WS, cmap=cmo.thermal)
        axs[0,1].set_xlabel("Longitude [$^\circ$E]")
        axs[0,1].set_ylabel("Latitude [$^\circ$N]")
        axs[0,1].set_title("Temperature")
        pmd = axs[1,0].scatter(WS_FT['longitudes'][:], WS_FT['latitudes'][:],\
                  c=WS_FT['sigmas'], \
                  vmax=sigma_max_WS, vmin=sigma_min_WS,cmap=cmo.dense)
        axs[1,0].set_xlabel("Longitude [$^\circ$E]")
        axs[1,0].set_ylabel("Latitude [$^\circ$N]")
        axs[1,0].set_title("Potential Density")
        pmp = axs[1,1].scatter(ADCP_WS['longitudes'][:], ADCP_WS['latitudes'][:],\
                  c=ADCP_WS['pm_vorticity'], \
                  vmax=PM_lims[-1],vmin=PM_lims[0],cmap=cmo.curl)
        axs[1,1].set_xlabel("Longitude [$^\circ$E]")
        axs[1,1].set_ylabel("Latitude [$^\circ$N]")
        axs[1,1].set_title("Poor Man's Vorticity [f]")
        fig.colorbar(pms, ax=axs[0,0])
        fig.colorbar(pmt, ax=axs[0,1])
        fig.colorbar(pmd, ax=axs[1,0])
        fig.colorbar(pmp, ax=axs[1,1])
        fig.suptitle("Walton Smith Surface Data" + ": " + start.strftime("%d-%b %H:%M") + " - " + end.strftime("%d-%b %H:%M"))
        fig.tight_layout()
        fig.savefig(os.path.join(directory,"WS_Surface_panels.png"),dpi=100)
        plt.close(fig)

def ASVSurface_png(ASVdata,start,end,directory,sal_lims=DEFAULT_LIMS,temp_lims=DEFAULT_LIMS,density_lims=DEFAULT_LIMS):
    """ASVdata is a dictionary of {"ASVname": data}"""

    for name, ASV in ASVdata.items():
        # print(ASV)
        if not temp_lims["lower"]:
            try:
                temp_min = np.nanmin(ASV["temperatures"])
            except ValueError: # empty list
                temp_min = -5
        else:
            temp_min = float(temp_lims["lowerLim"])
        if not temp_lims["upper"]:
            try:
                temp_max = np.nanmax(ASV["temperatures"])
            except ValueError: # empty list
                temp_max = 35
        else:
            temp_max = float(temp_lims["upperLim"])
        if not sal_lims["lower"]:
            try:
                sal_min = np.nanmin(ASV["salinities"])
            except ValueError: # empty list
                sal_min = -5
        else:
            sal_min = float(sal_lims["lowerLim"])
        if not sal_lims["upper"]:
            try:
                sal_max = np.nanmax(ASV["salinities"])
            except ValueError: # empty list
                sal_max = 35
        else:
            sal_max = float(sal_lims["upperLim"])
        if not density_lims["lower"]:
            try:
                sigma_min = np.nanmin(ASV["sigmas"])
            except ValueError: # empty list
                sigma_min = -5
        else:
            sigma_min = float(density_lims["lowerLim"])
        if not density_lims["upper"]:
            try:
                sigma_max = np.nanmax(ASV["sigmas"])
            except ValueError: # empty list
                sigma_max = 35
        else:
            sigma_max = float(density_lims["upperLim"])

        fig, axs = plt.subplots(2, 2, figsize=(12, 9))
        fig.subplots_adjust(left=0.02, bottom=0.06, right=0.95, top=0.94)
        pms = axs[0,0].scatter(ASV['longitudes'][:], ASV['latitudes'][:],\
                  c=ASV['salinities'], \
                   vmax=sal_max, vmin=sal_min, cmap=cmo.haline)
        axs[0,0].set_xlabel("Longitude [$^\circ$E]")
        axs[0,0].set_ylabel("Latitude [$^\circ$N]")
        axs[0,0].set_title("Salinity")
        pmt = axs[0,1].scatter(ASV['longitudes'][:], ASV['latitudes'][:],\
                  c=ASV['temperatures'], \
                   vmax=temp_max, vmin=temp_min, cmap=cmo.thermal)
        axs[0,1].set_xlabel("Longitude [$^\circ$E]")
        axs[0,1].set_ylabel("Latitude [$^\circ$N]")
        axs[0,1].set_title("Temperature")
        pmd = axs[1,0].scatter(ASV['longitudes'][:], ASV['latitudes'][:],\
                  c=ASV['sigmas'], \
                  vmax=sigma_max, vmin=sigma_min,cmap=cmo.dense)
        axs[1,0].set_xlabel("Longitude [$^\circ$E]")
        axs[1,0].set_ylabel("Latitude [$^\circ$N]")
        axs[1,0].set_title("Potential Density")
        # pmp = axs[1,1].scatter(ADCP_WS['longitudes'][:], ADCP_WS['latitudes'][:],\
        #           c=ADCP_WS['pm_vorticity'], \
        #           vmax=PM_lims[-1],vmin=PM_lims[0],cmap=cmo.curl)
        # axs[1,1].set_xlabel("Longitude [$^\circ$E]")
        # axs[1,1].set_ylabel("Latitude [$^\circ$N]")
        # axs[1,1].set_title("Poor Man's Vorticity [f]")
        fig.colorbar(pms, ax=axs[0,0])
        fig.colorbar(pmt, ax=axs[0,1])
        fig.colorbar(pmd, ax=axs[1,0])
        # fig.colorbar(pmp, ax=axs[1,1])
        fig.suptitle("ASV " + name + ": " + start.strftime("%d-%b %H:%M") + " - " + end.strftime("%d-%b %H:%M"))
        fig.tight_layout()
        fig.savefig(os.path.join(directory,"ASV_" + name + ".png"),dpi=100)
        plt.close(fig)

def ADCP_vector(filepath,start,end,directory,name,MAX_SPEED=1,VECTOR_LENGTH=1./20.,DEPTH_LEVELS=-1, CMAP=cmo.thermal):
    """Create ADCP vector"""

    rootgrp = netCDF4.Dataset(filepath, "r")
    decimal_days = rootgrp["time"]
    yearbase = rootgrp.yearbase

    # start = datetime.datetime.fromisoformat(START)
    # end = datetime.datetime.fromisoformat(END)

    # Turn times into datetimes
    times = []
    base_time = datetime.datetime(yearbase,1,1,tzinfo=datetime.timezone.utc)
    for dd in decimal_days[:]:
        dt = datetime.timedelta(days=dd)
        times.append(base_time + dt)



    idx = np.zeros(len(times),dtype=bool)
    for i in range(len(times)):
        idx[i] = (times[i] >= start) and (times[i] <= end)

    # Check empty time window
    times_filtered = [time for time, id in zip(times,idx) if id]

    if not times_filtered:
        # No data in time range
        return None

    # Get data
    lon = rootgrp["lon"][idx]
    lat = rootgrp["lat"][idx]
    u = rootgrp["u"][idx,:DEPTH_LEVELS]
    v = rootgrp["v"][idx,:DEPTH_LEVELS]
    missing = (u > 10**30) | (v > 10**30)
    u[missing] = 0
    v[missing] = 0
    depths = rootgrp["depth"][0,:DEPTH_LEVELS]
    depth_scaled = (depths - depths[0])/(depths[-1] - depths[0])

    folders = [f"{d:02.1f}m" for d in depths]

    colors = [CMAP(d) for d in depth_scaled]

    # print(rootgrp)

    kml.kml_vectors(directory,
    name+"_vector",
    lon,
    lat,
    u,
    v,
    times_filtered,
    folders=folders,
    color=colors,
    dmax=MAX_SPEED,
    vmax=VECTOR_LENGTH,
    compress=True
    )

def Hovmoller_Salinity(P_FT,WS_FT,ASV_data,start,end,directory,xaxis="latitudes",sal_lims=DEFAULT_LIMS):
    markers = iter(["p", "h", "^"])
    xlabels = {"latitudes": "Latitude [$^\circ$N]", "longitudes": "Longitude [$^\circ$E]"}

    if not sal_lims["lower"]:
        sal_min = min(np.nanmin(P_FT["salinities"]),np.nanmin(WS_FT["salinities"]))
        for ASV in ASV_data:
            sal_min = min(sal_min,np.nanmin(ASV_data[ASV]["salinities"]))
    else:
        sal_min = sal_lims["lowerLim"]
    if not sal_lims["upper"]:
        sal_max = max(np.nanmax(P_FT["salinities"]),np.nanmax(WS_FT["salinities"]))
        for ASV in ASV_data:
            sal_max = max(sal_max,np.nanmax(ASV_data[ASV]["salinities"]))
    else:
        sal_max = sal_lims["upperLim"]

    fig, ax = plt.subplots(figsize=(12,9))

    sc = ax.scatter(P_FT[xaxis],P_FT["times"],s=2,c=P_FT["salinities"],
        vmax=sal_max,vmin=sal_min,marker="o",cmap=cmo.haline)
    ax.annotate("P",(P_FT[xaxis][-1], P_FT["times"][-1]),
        textcoords="offset pixels", xytext=(5, 0), size=20)
    ax.scatter(WS_FT[xaxis],WS_FT["times"],s=2,c=WS_FT["salinities"],
        vmax=sal_max,vmin=sal_min,marker="s",cmap=cmo.haline)
    ax.annotate("WS",(WS_FT[xaxis][-1], WS_FT["times"][-1]),
        textcoords="offset pixels", xytext=(5, 0), size=20)

    for ASV in ASV_data:
        ax.scatter(ASV_data[ASV][xaxis],ASV_data[ASV]["times"],s=2,c=ASV_data[ASV]["salinities"],
            vmax=sal_max,vmin=sal_min,marker=next(markers),cmap=cmo.haline)
        ax.annotate(ASV,(ASV_data[ASV][xaxis][-1], ASV_data[ASV]["times"][-1]),
            textcoords="offset pixels", xytext=(5, 0), size=12)
    cb = plt.colorbar(sc)

    ax.set_title("Hovmoller Salinity " + start.strftime("%Y-%m-%d %H:%M:%S") + " - " + end.strftime("%Y-%m-%d %H:%M:%S"))
    ax.set_ylabel("Time")
    ax.set_xlabel(xlabels[xaxis])

    xlims = ax.get_xlim()
    x_min = min(np.nanmin(WS_FT[xaxis]),np.nanmin(P_FT[xaxis]))
    x_max = max(np.nanmax(WS_FT[xaxis]),np.nanmax(P_FT[xaxis]))
    x_min = max(xlims[0], 0.8*x_min)
    x_max = min(xlims[1], 1.2*x_max)
    ax.set_xlim([x_min,x_max])

    fig.tight_layout()
    fig.savefig(os.path.join(directory,"Hovmoller_Salinity.png"))

def Hovmoller_Temperature(P_FT,WS_FT,ASV_data,start,end,directory,xaxis="latitudes",temp_lims=DEFAULT_LIMS):
    markers = iter(["p", "h", "^"])
    xlabels = {"latitudes": "Latitude [$^\circ$N]", "longitudes": "Longitude [$^\circ$E]"}

    if not temp_lims["lower"]:
        temp_min = min(np.nanmin(P_FT["temperatures"]),np.nanmin(WS_FT["temperatures"]))
        for ASV in ASV_data:
            temp_min = min(temp_min,np.nanmin(ASV_data[ASV]["temperatures"]))
    else:
        temp_min = temp_lims["lowerLim"]
    if not temp_lims["upper"]:
        temp_max = max(np.nanmax(P_FT["temperatures"]),np.nanmax(WS_FT["temperatures"]))
        for ASV in ASV_data:
            temp_max = max(temp_max,np.nanmax(ASV_data[ASV]["temperatures"]))
    else:
        temp_max = temp_lims["upperLim"]

    fig, ax = plt.subplots(figsize=(12,9))

    sc = ax.scatter(P_FT[xaxis],P_FT["times"],s=2,c=P_FT["temperatures"],
        vmax=temp_max,vmin=temp_min,marker="o",cmap=cmo.thermal)
    ax.annotate("P",(P_FT[xaxis][-1], P_FT["times"][-1]),
        textcoords="offset pixels", xytext=(5, 0), size=20)
    ax.scatter(WS_FT[xaxis],WS_FT["times"],s=2,c=WS_FT["temperatures"],
        vmax=temp_max,vmin=temp_min,marker="s",cmap=cmo.thermal)
    ax.annotate("WS",(WS_FT[xaxis][-1], WS_FT["times"][-1]),
        textcoords="offset pixels", xytext=(5, 0), size=20)

    for ASV in ASV_data:
        ax.scatter(ASV_data[ASV][xaxis],ASV_data[ASV]["times"],s=2,c=ASV_data[ASV]["temperatures"],
            vmax=temp_max,vmin=temp_min,marker=next(markers),cmap=cmo.thermal)
        ax.annotate(ASV,(ASV_data[ASV][xaxis][-1], ASV_data[ASV]["times"][-1]),
            textcoords="offset pixels", xytext=(5, 0), size=12)
    cb = plt.colorbar(sc)

    ax.set_title("Hovmoller Temperature " + start.strftime("%Y-%m-%d %H:%M:%S") + " - " + end.strftime("%Y-%m-%d %H:%M:%S"))
    ax.set_ylabel("Time")
    ax.set_xlabel(xlabels[xaxis])

    xlims = ax.get_xlim()
    x_min = min(np.nanmin(WS_FT[xaxis]),np.nanmin(P_FT[xaxis]))
    x_max = max(np.nanmax(WS_FT[xaxis]),np.nanmax(P_FT[xaxis]))
    x_min = max(xlims[0], 0.8*x_min)
    x_max = min(xlims[1], 1.2*x_max)
    ax.set_xlim([x_min,x_max])

    fig.tight_layout()
    fig.savefig(os.path.join(directory,"Hovmoller_Temperature.png"))

def Hovmoller_Density(P_FT,WS_FT,ASV_data,start,end,directory,xaxis="latitudes",density_lims=DEFAULT_LIMS):
    markers = iter(["p", "h", "^"])
    xlabels = {"latitudes": "Latitude [$^\circ$N]", "longitudes": "Longitude [$^\circ$E]"}

    if not density_lims["lower"]:
        sigma_min = min(np.nanmin(P_FT["sigmas"]),np.nanmin(WS_FT["sigmas"]))
        for ASV in ASV_data:
            sigma_min = min(sigma_min,np.nanmin(ASV_data[ASV]["sigmas"]))
    else:
        sigma_min = density_lims["lowerLim"]
    if not density_lims["upper"]:
        sigma_max = max(np.nanmax(P_FT["sigmas"]),np.nanmax(WS_FT["sigmas"]))
        for ASV in ASV_data:
            sigma_max = max(sigma_max,np.nanmax(ASV_data[ASV]["sigmas"]))
    else:
        sigma_max = density_lims["upperLim"]

    fig, ax = plt.subplots(figsize=(12,9))

    sc = ax.scatter(P_FT[xaxis],P_FT["times"],s=2,c=P_FT["sigmas"],
        vmax=sigma_max,vmin=sigma_min,marker="o",cmap=cmo.dense)
    ax.annotate("P",(P_FT[xaxis][-1], P_FT["times"][-1]),
        textcoords="offset pixels", xytext=(5, 0), size=20)
    ax.scatter(WS_FT[xaxis],WS_FT["times"],s=2,c=WS_FT["sigmas"],
        vmax=sigma_max,vmin=sigma_min,marker="s",cmap=cmo.dense)
    ax.annotate("WS",(WS_FT[xaxis][-1], WS_FT["times"][-1]),
        textcoords="offset pixels", xytext=(5, 0), size=20)

    for ASV in ASV_data:
        ax.scatter(ASV_data[ASV][xaxis],ASV_data[ASV]["times"],s=2,c=ASV_data[ASV]["sigmas"],
            vmax=sigma_max,vmin=sigma_min,marker=next(markers),cmap=cmo.dense)
        ax.annotate(ASV,(ASV_data[ASV][xaxis][-1], ASV_data[ASV]["times"][-1]),
            textcoords="offset pixels", xytext=(5, 0), size=12)
    cb = plt.colorbar(sc)

    ax.set_title("Hovmoller Potential Density " + start.strftime("%Y-%m-%d %H:%M:%S") + " - " + end.strftime("%Y-%m-%d %H:%M:%S"))
    ax.set_ylabel("Time")
    ax.set_xlabel(xlabels[xaxis])

    xlims = ax.get_xlim()
    x_min = min(np.nanmin(WS_FT[xaxis]),np.nanmin(P_FT[xaxis]))
    x_max = max(np.nanmax(WS_FT[xaxis]),np.nanmax(P_FT[xaxis]))
    x_min = max(xlims[0], 0.8*x_min)
    x_max = min(xlims[1], 1.2*x_max)
    ax.set_xlim([x_min,x_max])

    fig.tight_layout()
    fig.savefig(os.path.join(directory,"Hovmoller_Density.png"))

def MET_Summary(Pelican_nc,WS_nc,start,end,directory):
    pelican = netCDF4.Dataset(Pelican_nc)
    walton_smith = netCDF4.Dataset(WS_nc)
    start_sec = (start - datetime.datetime(year=2021,month=1,day=1,tzinfo=datetime.timezone.utc)).total_seconds()
    end_sec = (end - datetime.datetime(year=2021,month=1,day=1,tzinfo=datetime.timezone.utc)).total_seconds()

    p_idx = (pelican["time"][:] >= start_sec) & (pelican["time"][:] <= end_sec)
    p_times = pelican["time"][p_idx]
    p_times = [datetime.datetime(year=2021,month=1,day=1,tzinfo=datetime.timezone.utc) + datetime.timedelta(seconds=t) for t in p_times]
    p_AirTemp = pelican["AirTemp"][p_idx]
    p_BaroPressure = pelican["BaroPressure"][p_idx]
    p_RelHumidity = pelican["RelHumidity"][p_idx]
    p_WindDirection = pelican["WindDirection"][p_idx]
    p_WindSpeed = pelican["WindSpeed"][p_idx]

    WS_idx = (walton_smith["Date"][:] >= start_sec) & (walton_smith["Date"][:] <= end_sec)
    WS_times = walton_smith["Date"][WS_idx]
    WS_times = [datetime.datetime(year=2021,month=1,day=1,tzinfo=datetime.timezone.utc) + datetime.timedelta(seconds=t) for t in WS_times]
    WS_AirTemp = walton_smith["AirTemp"][WS_idx]
    WS_BaroPressure = walton_smith["BaroPressure"][WS_idx]
    WS_RelHumidity = walton_smith["RelHumidity"][WS_idx]
    WS_WindDirection = walton_smith["WindDirection"][WS_idx]
    WS_WindSpeed = walton_smith["WindSpeed"][WS_idx]

    fig, axs = plt.subplots(5,1,sharex=True,figsize=(12,9),constrained_layout=True)

    axs[0].plot(p_times,p_WindSpeed,'b')
    axs[0].plot(WS_times,WS_WindSpeed,'g')
    axs[0].set_ylabel("Wind Speed\n[m/s]")

    axs[1].plot(p_times,p_WindDirection,'b')
    axs[1].plot(WS_times,WS_WindDirection,'g')
    axs[1].set_ylabel("Wind Direction\n[$^\circ$]")

    axs[2].plot(p_times,p_AirTemp,'b')
    axs[2].plot(WS_times,WS_AirTemp,'g')
    axs[2].set_ylabel("Air Temp.\n[$^\circ$C]")

    axs[3].plot(p_times,p_BaroPressure,'b')
    axs[3].plot(WS_times,WS_BaroPressure,'g')
    axs[3].set_ylabel("Barometric Pressure\n[mbar]")

    axs[4].plot(p_times,p_RelHumidity,'b')
    axs[4].plot(WS_times,WS_RelHumidity,'g')
    axs[4].set_ylabel("Relative Humidity\n[%]")

    axs[4].set_xlabel("Time")

    fig.suptitle("Met Summary - Pelican (blue), Walton Smith (Green): " + start.strftime("%Y-%m-%d %H:%M:%S") + " - " + end.strftime("%Y-%m-%d %H:%M:%S"))
    fig.savefig(os.path.join(directory,"met_summary.png"))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("fn", type=str, help="ASV file to process")
    parser.add_argument("start", type=str, help="Starting timestamp")
    parser.add_argument("end", type=str, help="Ending timestamp")
    args = parser.parse_args()

    try:
        parse_ASV(args.fn, args.start, args.end)
    except Exception as e:
        logging.exception("Exception for %s", args)
