#! /usr/bin/python3
#
# Sample for how to access the ASV database for Jamie
#
# Jul-2021, Pat Welch

import argparse
import datetime
import sqlite3
import pandas as pd

parser = argparse.ArgumentParser()
parser.add_argument("--db", type=str, required=True, help="SQLite3 database to access")
parser.add_argument("--etime", type=str, 
        default=datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        help="End of time interval")
parser.add_argument("--dt", type=float, default=48, help="Length of interval in hours")
parser.add_argument("--tbl", type=str, required=True, choices=("nav", "ctd", "adcp"),
        help="Database table to read")
args = parser.parse_args()

timeFormat = "%Y-%m-%d %H:%M:%S"
etime = datetime.datetime.strptime(args.etime, timeFormat)
stime = etime - datetime.timedelta(hours=args.dt)

sql = "SELECT DISTINCT boat FROM nav;"
boats = pd.read_sql_query(sql, sqlite3.connect(args.db))
print(boats)

columns = {
        "nav": ("t", "latitude", "longitude"),
        "ctd": ("t", "temperature", "salinity"),
        "adcp": ("t", "u", "v", "w"),
        }

for boat in boats.boat:
    print("Working on", boat)
    sql = "SELECT " + ",".join(columns[args.tbl]) + " FROM " + args.tbl
    sql+= " WHERE boat='" + boat + "'"
    sql+= " AND t>='" + stime.strftime(timeFormat) + "'"
    sql+= " AND t<='" + etime.strftime(timeFormat) + "'"
    sql+= " AND strftime('%S', t)='00'"
    sql+= " ORDER BY t;"
    print(sql)
    df = pd.read_sql_query(sql, sqlite3.connect(args.db))
    print(df)
