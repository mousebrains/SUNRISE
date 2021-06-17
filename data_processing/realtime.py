import yaml
import argparse
import os
import sys
from datetime import datetime, timezone

import sunrise

# DATAPATHS
PELICAN_600_DATA = "/Users/megangan/Desktop/Cruise/TwoShips_test/Pelican_data/wh300.nc"
PELICAN_1200_DATA = "/Users/megangan/Desktop/Cruise/TwoShips_test/Pelican_data/wh1200.nc"
WS_600_DATA = "/Users/megangan/Desktop/Cruise/TwoShips_test/WS_data/wh600.nc"
WS_1200_DATA = "/Users/megangan/Desktop/Cruise/TwoShips_test/WS_data/wh1200.nc"
OUTPUT_PATH = "/Users/megangan/Desktop/Cruise/TwoShips_test/Processed"

parser = argparse.ArgumentParser()
parser.add_argument("fn", nargs="+", help="Input yaml files")
args = parser.parse_args()

for fn in args.fn:
    with open(fn, "r") as fp:
        print(fn)
        input = yaml.safe_load(fp)
        print(input)

# parse start and end
try:
    start = input["start"]

    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)

    end = input["end"]

    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
except:
    raise
    sys.exit("Invalid start or end time. Times should be in isoformat: " +
    "'YYYY-mm-ddTHH:MM:SS' or 'YYYY-mm-ddTHH:MM:SSzzzzzz'")

# Construct a directory
try:
    directory = os.path.join(OUTPUT_PATH,
        datetime.utcnow().strftime("%m%d-%H%M_") + input["short_name"])
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

# First the throughflow variables
salinity = input["salinity_kmz"] or input["salinity_png"]
temperature = input["temperature_kmz"] or input["temperature_png"]
density = input["density_kmz"] or input["density_png"]
kmz = input["salinity_kmz"] or input["temperature_kmz"] or input["density_kmz"]
png = input["salinity_png"] or input["temperature_png"] or input["density_png"]
sal_lims = input.pop("sal_lims",None)
temp_lims = input.pop("temp_lims",None)
density_lims = input.pop("density_lims",None)

FT = sunrise.throughflow(start,end,directory,salinity=salinity,temperature=temperature,density=density,kmz=kmz,png=png,
    sal_lims=sal_lims,temp_lims=temp_lims,density_lims=density_lims)

# Next Poor Man's Vorticity
if any([input["PMV_kmz"], input["PMV_png"], input["Pelican_surface"], input["WS_surface"]]):
    Pelican_PMV = sunrise.ADCP_PMV(PELICAN_1200_DATA,start,end,directory,
        pmv_filename="Pelican_PMV",label="Pelican PMV [f]",kmz=input["PMV_kmz"])
    WS_PMV = sunrise.ADCP_PMV(WS_1200_DATA,start,end,directory,
        pmv_filename="Walton_Smith_PMV",label="WS PMV [f]",kmz=input["PMV_kmz"])

# Now surface summary plots
if input["Pelican_surface"] or input["WS_surface"]:
    sunrise.ShipSurface_png(FT,Pelican_PMV,WS_PMV,start,end,directory,
        plot_P=input["Pelican_surface"], plot_WS=input["WS_surface"],
        sal_lims=sal_lims, temp_lims=temp_lims, density_lims=density_lims)

# ADCP sections
if input["Pelican_600kHz_section"]:
    sunrise.ADCP_section(PELICAN_600_DATA,start,end,directory,"Pelican 600kHz",maxdepth=60)
if input["Pelican_1200kHz_section"]:
    sunrise.ADCP_section(PELICAN_1200_DATA,start,end,directory,"Pelican 1200kHz",maxdepth=15)
if input["WS_600kHz_section"]:
    sunrise.ADCP_section(WS_600_DATA,start,end,directory,"WS 600kHz",maxdepth=60)
if input["WS_1200kHz_section"]:
    sunrise.ADCP_section(WS_1200_DATA,start,end,directory,"WS 1200kHz",maxdepth=15)

# ADCP vectors
if input["Pelican_600kHz_vector"]:
    sunrise.ADCP_vector(PELICAN_600_DATA,start,end,directory,"Pelican 600kHz",MAX_SPEED=None,VECTOR_LENGTH=1./20.,DEPTH_LEVELS=5)
if input["Pelican_1200kHz_vector"]:
    sunrise.ADCP_vector(PELICAN_1200_DATA,start,end,directory,"Pelican 1200kHz",MAX_SPEED=None,VECTOR_LENGTH=1./20.,DEPTH_LEVELS=5)
if input["WS_600kHz_vector"]:
    sunrise.ADCP_vector(WS_600_DATA,start,end,directory,"WS 600kHz",MAX_SPEED=None,VECTOR_LENGTH=1./20.,DEPTH_LEVELS=5)
if input["WS_1200kHz_vector"]:
    sunrise.ADCP_vector(WS_1200_DATA,start,end,directory,"WS 1200kHz",MAX_SPEED=None,VECTOR_LENGTH=1./20.,DEPTH_LEVELS=5)
