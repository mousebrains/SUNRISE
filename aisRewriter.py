#! /usr/bin/python3
#
# Read in a JSON file and spit out a CSV file
#
# June-2021, Pat Welch, pat@mousebrains

import json
import argparse
import datetime

parser = argparse.ArgumentParser()
parser.add_argument("json", type=str, help="Input AIS json filename")
parser.add_argument("csv", type=str, help="Output AIS csv filename")
parser.add_argument("output", type=str, help="Output AIS compact json filename")
args = parser.parse_args()

qSeen = set()

with open(args.json, "r") as ifp, open(args.csv, "w") as ofp, open(args.output, "w") as jfp:
    ofp.write("t,mmsi,lat,lon,sog,cog\n");
    prevHour = None
    prevMin = None
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    tNow = now.time()
    dNow = now.date()

    for line in ifp:
        info = json.loads(line)

        if ("timestamp" not in info) or \
                ("mmsi" not in info) or \
                ("x" not in info) or \
                ("y" not in info): 
            continue

        if "utc_min" in info: prevMin = info["utc_min"]
        if "utc_hour" in info: prevHour = info["utc_hour"]

        ident = []
        for key in sorted(info): ident.append(str(info[key]))
        ident = ":".join(ident)
        if ident in qSeen: continue
        qSeen.add(ident)

        if prevHour is None or prevMin is None: continue # Don't know the hour or minute yet

        t = datetime.datetime.combine(dNow,
                datetime.time(prevHour, prevMin, info["timestamp"] % 60, 
                    tzinfo=datetime.timezone.utc))

        if t > now: t -= datetime.timedelta(days=1) # Clock wrap

        row = [int(round(t.timestamp(),0)), info["mmsi"],
                round(info["y"], 6), round(info["x"], 6)]
        item = {"t":row[0], 
                "mmsi": row[1],
                "y": row[2],
                "x": row[3],
                }
        if "sog" in info:
            row.append(round(info["sog"],1))
            item["sog"] = row[-1]
        else:
            row.append("")

        if "cog" in info:
            row.append(int(round(info["cog"],0)))
            item["cog"] = row[-1]
        else:
            row.append("")

        ofp.write(",".join(map(str, row)) + "\n")
        jfp.write(json.dumps(item, separators=(',', ':')) + "\n")
