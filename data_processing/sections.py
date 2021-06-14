import netCDF4
import datetime
import numpy as np
import cmocean.cm as cmo
import matplotlib.pyplot as plt
import matplotlib.gridspec as gs
import matplotlib.units as munits
import matplotlib.dates as mdates
from matplotlib.ticker import AutoMinorLocator, MaxNLocator
import sys
import os
from geopy.distance import distance
from scipy.signal import savgol_filter

CORIOLIS = 7*10**-5

def ADCP_sections(filepath,directory,name,start,end,maxdepth=60):
    """Create ADCP sections"""

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
    heading = rootgrp["heading"][idx] # bearing in degrees clockwise

    ship_speed = (uship**2 + vship**2)**0.5

    # deal with missing data points
    u[u > 10**30] = np.nan
    v[v > 10**30] = np.nan

    #shear
    ushear = np.gradient(u,depths_use,axis=1)
    vshear = np.gradient(v,depths_use,axis=1)
    # angle = np.angle(u+1j*v)

    # calculate distances
    distances = np.empty(lat.shape,dtype=np.float64)
    for i in range(lat.size):
        distances[i] = distance((lat[i],lon[i]),(lat[0],lon[0])).km*1000

    # ship perpendicular velocity
    heading_grad = np.abs(np.gradient(np.sin(heading*np.pi/180),distances)) + np.abs(np.gradient(np.cos(heading*np.pi/180),distances))
    heading_change = heading_grad > 0.01
    spv = v*np.sin(heading[:,None]*np.pi/180) - u*np.cos(heading[:,None]*np.pi/180)
    spv[heading_change,:] = np.nan
    spv[ship_speed<1] = np.nan
    pm_velocity = savgol_filter(spv,7,1,deriv=1,axis=0)
    pm_distance = savgol_filter(distances,7,1,deriv=1)
    pm_vorticity = pm_velocity/pm_distance[:,None]/CORIOLIS
    # pm_vorticity[heading_change,:] = np.nan
    # pm_vorticity[ship_speed<1] = np.nan
    #pm_vorticity = np.gradient(spv,distances,axis=0)/CORIOLIS

    pmv_nonan = pm_vorticity[~np.isnan(pm_vorticity)]

    pmv_5, pmv_95 = np.percentile(pmv_nonan,[5,95])

    # ******************** Get Limits *********************************** #
    vel_max = max(np.nanmax(u),np.nanmax(v),np.nanmax(-u),np.nanmax(-v))
    shear_max = max(np.nanmax(ushear), np.nanmax(vshear), np.nanmax(-ushear), np.nanmax(-vshear))
    pmv_max = max(pmv_95, -pmv_5)
    # ******************* Make Plots ************************************ #

    converter = mdates.ConciseDateConverter()
    munits.registry[datetime.datetime] = converter

    fig1 = plt.figure(figsize=(12, 6),constrained_layout=True)
    gs1 = gs.GridSpec(2, 2, figure=fig1, width_ratios=[1,1])

    axu=fig1.add_subplot(gs1[0,0])
    pu = axu.pcolor(times_use,depths_use,u.T,cmap=cmo.balance,shading='nearest',vmin=-vel_max, vmax=vel_max)
    axu.xaxis_date()
    axu.invert_yaxis()
    axu.set_ylabel("Depth [m]")
    cb = plt.colorbar(pu,ax=axu)
    axu.set_title("$u$ [m/s]")

    axv=fig1.add_subplot(gs1[1,0])
    pv = axv.pcolor(times_use,depths_use,v.T,cmap=cmo.balance,shading='nearest',vmin=-vel_max, vmax=vel_max)
    axv.xaxis_date()
    axv.invert_yaxis()
    axv.set_ylabel("Depth [m]")
    cb = plt.colorbar(pv,ax=axv)
    axv.set_title("$v$ [m/s]")


    axpos = fig1.add_subplot(gs1[0,1])
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
    axpmv = fig1.add_subplot(gs1[1,1])
    ppmv = axpmv.pcolor(times_use,depths_use,pm_vorticity.T,cmap=cmo.balance,shading="nearest",vmin=-pmv_max,vmax=pmv_max)
    axpmv.xaxis_date()
    axpmv.invert_yaxis()
    axpmv.set_ylabel("Depth [m]")
    cb = plt.colorbar(ppmv,ax=axpmv)
    axpmv.set_title("Poor Man's Vorticity [$f$]")

    fig1.suptitle(name + ": " + start.strftime("%d-%b %H:%M") + " - " + end.strftime("%d-%b %H:%M"))
    fig1.savefig(os.path.join(directory,name + "_velocity.png"))

    fig2 = plt.figure(figsize=(12, 6),constrained_layout=True)
    gs2 = gs.GridSpec(2, 2, figure=fig2, width_ratios=[1,1])

    axuz = fig2.add_subplot(gs2[0,:])
    puz = axuz.pcolor(times_use,depths_use,ushear.T,cmap=cmo.balance,shading="nearest",vmin=-shear_max,vmax=shear_max)
    axuz.xaxis_date()
    axuz.invert_yaxis()
    axuz.set_ylabel("Depth [m]")
    cb = plt.colorbar(puz,ax=axuz)
    axuz.set_title("$u_z$ [1/s]")

    axvz = fig2.add_subplot(gs2[1,:])
    pvz = axvz.pcolor(times_use,depths_use,vshear.T,cmap=cmo.balance,shading="nearest",vmin=-shear_max,vmax=shear_max)
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
