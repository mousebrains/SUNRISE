#! /usr/bin/python3
#
# Filter a shapefile by a latitude/longitude bounding box
# and by attribute filtering.
#
# June-2021, Pat Welch, pat@mousebrains.com

import argparse
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon

parser = argparse.ArgumentParser()
parser.add_argument("--input", type=str, required=True, help="Input shapefile")
grp = parser.add_mutually_exclusive_group(required=True)
grp.add_argument("--clip", action="store_true", help="Only clip data")
grp.add_argument("--filter", type=str, help="Field to filter on null values")
grp = parser.add_argument_group(description="Filter output results")
grp.add_argument("--null", type=str, help="null results saved here")
grp.add_argument("--notNull", type=str, help="notNull results saved here")
grp = parser.add_argument_group(description="Bounding box")
grp.add_argument("--latMin", type=float, default=28.4, help="Minimum latitude")
grp.add_argument("--latMax", type=float, default=29.3, help="Maximum latitude")
grp.add_argument("--lonMin", type=float, default=-94.4, help="Minimum longitude")
grp.add_argument("--lonMax", type=float, default=-91.4, help="Maximum longitude")
grp.add_argument("--output", type=str, help="Output filename for just clipped results")
args = parser.parse_args()

bbox = pd.DataFrame({
    "latitude":  [args.latMin, args.latMin, args.latMax, args.latMax],
    "longitude": [args.lonMin, args.lonMax, args.lonMax, args.lonMin],
    });
bbox = Polygon(gpd.points_from_xy(bbox.longitude, bbox.latitude))
print("Reading", args.input)
a = gpd.read_file(args.input)
b = gpd.clip(a, bbox) # Clip to the region of interest
print("Clipped from", a.shape[0], "to", b.shape[0], "rows")

if args.clip: # Just clip
    if args.output is None:
        parser.error("--output required with --clip")
    b.to_file(args.output)
else: # Filter
    if args.filter not in b:
        parser.error("Filter " + args.filter + " not known")
    if args.null is None and args.notNull is None:
        parser.error("--null and/or --notNull must be specified with --filter")
    bNull = b.loc[b[args.filter].isnull()]
    bNot  = b.loc[b[args.filter].notnull()]
    print("Null", bNull.shape[0], "Not Null", bNot.shape[0])
    if args.null: bNull.to_file(args.null)
    if args.notNull: bNot.to_file(args.notNull)
