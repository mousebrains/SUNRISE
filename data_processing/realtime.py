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
    if isinstance(input["start"],str):
        start = datetime.fromisoformat(input["start"])
    else:
        start = input["start"]

    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)

    if isinstance(input["stop"],str):
        end = datetime.fromisoformat(input["stop"])
    else:
        end = input["stop"]

    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
except:
    raise
    sys.exit("Invalid start or end time. Times should be in isoformat: " +
    "'YYYY-mm-ddTHH:MM:SS' or 'YYYY-mm-ddTHH:MM:SSzzzzzz'")

# Construct a directory
if input.pop("rolling",False):
    directory = os.path.join(OUT_DIRECTORY,"Rolling-2Days")
else:
    try:
        directory = os.path.join(OUT_DIRECTORY,
            start.strftime("%Y-%m-%dT%H:%M_") + end.strftime("%Y-%m-%dT%H:%M_") + input["name"].strip() + datetime.utcnow().strftime("_%m-%dT%H:%M"))
        print(directory)
        os.mkdir(directory)
    except:
        raise
        sys.exit("Directory Creation Failed")

# Write the description to a text file in the directory
try:
    with open(os.path.join(directory,"0.description.txt"),"w") as f:
        f.write(input["description"])
        f.write("\n\n** Comments ** \n")
        f.write(input["comment"])
except:
    raise
    print("Description file not created")

# First the limits
sal_lims = input["limits"][0]["sal_lims"]
temp_lims = input["limits"][1]["temp_lims"]
density_lims = input["limits"][2]["density_lims"]

plots_list = input["plots"]
plots = {}
for dict in plots_list:
    for key, value in dict.items():
        plots[key] = value
# Now get the throughflow variables
try:
    if any([plots["salinity_kmz"], plots["temperature_kmz"], plots["density_kmz"],
        plots["salinity_png"], plots["temperature_png"], plots["density_png"],
        plots["sal_grad_kmz"], plots["sal_grad_png"],
        plots["Pelican_surface"], plots["WS_surface"]]):
        P_FT = sunrise.parse_PFT(PELICAN_FT_DATAPATHS,start,end)
        WS_FT = sunrise.parse_WSFT(WS_FT_DATAPATH,start,end)
        # print(WS_FT)


        # Make throughflow plots
        sunrise.throughflow(P_FT,WS_FT,start,end,directory,
            sal_kmz=plots["salinity_kmz"],temp_kmz=plots["temperature_kmz"],density_kmz=plots["density_kmz"],
        sal_png=plots["salinity_png"],temp_png=plots["temperature_png"],density_png=plots["density_png"],
        salg_kmz=plots["sal_grad_kmz"], salg_png=plots["sal_grad_png"],
        sal_lims=sal_lims,temp_lims=temp_lims,density_lims=density_lims)
except:
    raise

# Next Get Poor Man's Vorticity and make kmzs
try:
    if any([plots["PMV_kmz"], plots["pmv_png"], plots["Pelican_surface"], plots["WS_surface"]]):
        P_PMV = sunrise.ADCP_PMV(PELICAN_1200_DATA,start,end,directory,
            pmv_filename="Pelican_PMV",label="Pelican PMV [f]",kmz=plots["PMV_kmz"])
        WS_PMV = sunrise.ADCP_PMV(WS_1200_DATA,start,end,directory,
            pmv_filename="WS_PMV",label="WS PMV [f]",kmz=plots["PMV_kmz"])

    if plots["pmv_png"]:
        sunrise.PMV_png(start,end,directory,P_PMV,WS_PMV)
except:
    raise

# Now surface summary plots
try:
    if plots["Pelican_surface"] or plots["WS_surface"]:
        sunrise.ShipSurface_png(P_FT,WS_FT,P_PMV,WS_PMV,start,end,directory,
            plot_P=plots["Pelican_surface"], plot_WS=plots["WS_surface"],
            sal_lims=sal_lims, temp_lims=temp_lims, density_lims=density_lims)
except:
    raise

# ADCP sections
try:
    if plots["Pelican_600kHz_section"]:
        sunrise.ADCP_section(PELICAN_600_DATA,start,end,directory,"Pelican 600kHz",maxdepth=60)
    if plots["Pelican_1200kHz_section"]:
        sunrise.ADCP_section(PELICAN_1200_DATA,start,end,directory,"Pelican 1200kHz",maxdepth=15)
    if plots["WS_600kHz_section"]:
        sunrise.ADCP_section(WS_600_DATA,start,end,directory,"WS 600kHz",maxdepth=60)
    if plots["WS_1200kHz_section"]:
        sunrise.ADCP_section(WS_1200_DATA,start,end,directory,"WS 1200kHz",maxdepth=15)
except:
    raise

# ADCP vectors
try:
    if plots["Pelican_600kHz_vector"]:
        sunrise.ADCP_vector(PELICAN_600_DATA,start,end,directory,"Pelican 600kHz",DEPTH_LEVELS=5)
    if plots["Pelican_1200kHz_vector"]:
        sunrise.ADCP_vector(PELICAN_1200_DATA,start,end,directory,"Pelican 1200kHz",DEPTH_LEVELS=5)
    if plots["WS_600kHz_vector"]:
        sunrise.ADCP_vector(WS_600_DATA,start,end,directory,"WS 600kHz",DEPTH_LEVELS=5)
    if plots["WS_1200kHz_vector"]:
        sunrise.ADCP_vector(WS_1200_DATA,start,end,directory,"WS 1200kHz",DEPTH_LEVELS=5)
except:
    raise
