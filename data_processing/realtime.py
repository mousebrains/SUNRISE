import yaml
import argparse
import os
import sys
from datetime import datetime, timezone

import sunrise

# DATAPATHS
OUT_DIRECTORY ="/home/pat/Processed"
PELICAN_FT_DATAPATHS = ["/home/pat/Dropbox/Pelican/test/MIDAS/MIDAS_008.elg"]
WS_FT_DATAPATH = "/home/pat/Dropbox/WaltonSmith/test/WS21163_Hetland_TR-Full-Vdl.dat"
PELICAN_600_DATA = "/home/pat/Dropbox/Pelican/test/ADCP/wh300.nc"
PELICAN_1200_DATA = "/home/pat/Dropbox/Pelican/test/ADCP/wh1200.nc"
WS_600_DATA = "/home/pat/Dropbox/WaltonSmith/test/wh600.nc"
WS_1200_DATA = "/home/pat/Dropbox/WaltonSmith/test/wh600.nc"


parser = argparse.ArgumentParser()
parser.add_argument("fn", nargs="+", help="Input yaml files")
args = parser.parse_args()

for fn in args.fn:
    with open(fn, "r") as fp:
        input = yaml.safe_load(fp)

# parse start and end
try:
    start = datetime.fromisoformat(input["start"])

    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)

    end = datetime.fromisoformat(input["end"])

    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
except:
    raise
    sys.exit("Invalid start or end time. Times should be in isoformat: " +
    "'YYYY-mm-ddTHH:MM:SS' or 'YYYY-mm-ddTHH:MM:SSzzzzzz'")

# Construct a directory
try:
    directory = os.path.join(OUT_DIRECTORY,
        start.strftime("%Y-%m-%dT%H:%M_") + end.strftime("%Y-%m-%dT%H:%M_") + input["short_name"].strip() + datetime.utcnow().strftime("_%m%d-%H%M"))
    print(directory)
    os.mkdir(directory)
except:
    raise
    sys.exit("Directory Creation Failed")

# Write the description to a text file in the directory
try:
    with open(os.path.join(directory,"0.description.txt"),"w") as f:
        f.write(input["description"])
except:
    raise
    print("Description file not created")

# First the limits
sal_lims = input["limits"][0]["sal_limits"]
temp_lims = input["limits"][1]["temp_limits"]
density_lims = input["limits"][2]["density_limits"]

# Now get the throughflow variables
try:
    if any([input["salinity_kmz"], input["temperature_kmz"], input["density_kmz"],
        input["salinity_png"], input["temperature_png"], input["density_png"],
        input["sal_grad_kmz"], input["sal_grad_png"],
        input["Pelican_surface"], input["WS_surface"]]):
        P_FT = sunrise.parse_PFT(PELICAN_FT_DATAPATHS,start,end)
        WS_FT = sunrise.parse_WSFT(WS_FT_DATAPATH,start,end)
        # print(WS_FT)


    # Make throughflow plots
    sunrise.throughflow(P_FT,WS_FT,start,end,directory,
        sal_kmz=input["salinity_kmz"],temp_kmz=input["temperature_kmz"],density_kmz=input["density_kmz"],
        sal_png=input["salinity_png"],temp_png=input["temperature_png"],density_png=input["density_png"],
        salg_kmz=input["sal_grad_kmz"], salg_png=input["sal_grad_png"],
        sal_lims=sal_lims,temp_lims=temp_lims,density_lims=density_lims)
except:
    raise

# Next Get Poor Man's Vorticity and make kmzs
try:
    if any([input["PMV_kmz"], input["PMV_png"], input["Pelican_surface"], input["WS_surface"]]):
        P_PMV = sunrise.ADCP_PMV(PELICAN_1200_DATA,start,end,directory,
            pmv_filename="Pelican_PMV",label="Pelican PMV [f]",kmz=input["PMV_kmz"])
        WS_PMV = sunrise.ADCP_PMV(WS_1200_DATA,start,end,directory,
            pmv_filename="WS_PMV",label="WS PMV [f]",kmz=input["PMV_kmz"])

    if input["PMV_png"]:
        sunrise.PMV_png(start,end,directory,P_PMV,WS_PMV)
except:
    raise

# Now surface summary plots
try:
    if input["Pelican_surface"] or input["WS_surface"]:
        sunrise.ShipSurface_png(P_FT,WS_FT,P_PMV,WS_PMV,start,end,directory,
            plot_P=input["Pelican_surface"], plot_WS=input["WS_surface"],
            sal_lims=sal_lims, temp_lims=temp_lims, density_lims=density_lims)
except:
    raise

# ADCP sections
try:
    if input["Pelican_600kHz_section"]:
        sunrise.ADCP_section(PELICAN_600_DATA,start,end,directory,"Pelican 600kHz",maxdepth=60)
    if input["Pelican_1200kHz_section"]:
        sunrise.ADCP_section(PELICAN_1200_DATA,start,end,directory,"Pelican 1200kHz",maxdepth=15)
    if input["WS_600kHz_section"]:
        sunrise.ADCP_section(WS_600_DATA,start,end,directory,"WS 600kHz",maxdepth=60)
    if input["WS_1200kHz_section"]:
        sunrise.ADCP_section(WS_1200_DATA,start,end,directory,"WS 1200kHz",maxdepth=15)
except:
    raise

# ADCP vectors
try:
    if input["Pelican_600kHz_vector"]:
        sunrise.ADCP_vector(PELICAN_600_DATA,start,end,directory,"Pelican 600kHz",DEPTH_LEVELS=5)
    if input["Pelican_1200kHz_vector"]:
        sunrise.ADCP_vector(PELICAN_1200_DATA,start,end,directory,"Pelican 1200kHz",DEPTH_LEVELS=5)
    if input["WS_600kHz_vector"]:
        sunrise.ADCP_vector(WS_600_DATA,start,end,directory,"WS 600kHz",DEPTH_LEVELS=5)
    if input["WS_1200kHz_vector"]:
        sunrise.ADCP_vector(WS_1200_DATA,start,end,directory,"WS 1200kHz",DEPTH_LEVELS=5)
except:
    raise
