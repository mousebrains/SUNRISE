import yaml
import argparse
import os
import sys
from datetime import datetime, timezone

import sunrise

# DATAPATHS
PELICAN_300_DATA = r"C:\Users\hildi\Documents\Stanford\Research\Sunrise\underway_data\wh300.nc"
PELICAN_1200_DATA = r"C:\Users\hildi\Documents\Stanford\Research\Sunrise\underway_data\wh1200.nc"

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
    directory = os.path.join(r"C:\Users\hildi\Documents\Stanford\Research\Sunrise\Processed",
        input["submitter"] + "_" + str(datetime.utcnow().timestamp()))
    print(directory)
    os.mkdir(directory)
except:
    raise
    sys.exit("Directory Creation Failed")

# Write the description to a text file in the directory
try:
    with open(os.path.join(directory,"description.txt"),"w") as f:
        f.write(input["description"])
except:
    raise
    print("Description file not created")

# For every option in options we create the requested plot
# Pelican 300khz ADCP
if "P300" in input["options"]:
    try:
        fig_vel, fig_shear = sunrise.ADCP_section(PELICAN_300_DATA,"Pelican 300khz",start,end,maxdepth=60)
        fig_vel.savefig(os.path.join(directory,"Pelican_300_vel.png"))
        fig_shear.savefig(os.path.join(directory,"Pelican_300_shear.png"))
        input["options"].remove("P300")
    except:
        raise
        print("P300 failed")

# Pelican 1200khz ADCP
if "P1200" in input["options"]:
    try:
        fig_vel, fig_shear = sunrise.ADCP_section(PELICAN_1200_DATA,"Pelican 1200khz",start,end,maxdepth=15)
        fig_vel.savefig(os.path.join(directory,"Pelican_1200_vel.png"))
        fig_shear.savefig(os.path.join(directory,"Pelican_1200_shear.png"))
        input["options"].remove("P1200")
    except:
        raise
        print("P1200 failed")

# Followed by the rest of the options: WS ADCPs, throughflow plots, kml file generators

# Once we have gone through all the different plot options check that input"options" is empty

for option in input["options"]:
    print(f"{option} is not a valid option")
