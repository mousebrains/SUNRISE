#! /usr/bin/env python3
#
# Grab all the GPS fixes from Pacific Gyre for the Carthe floats
#
# Apr-2021, Pat Welch, pat@mousebrains
#
import MyLogger
import logging
import argparse
import requests
import pandas as pd
import time
import re
import sqlite3
import math
import datetime

def mkTable(cur:sqlite3.Cursor, tblName:str, logger:logging.Logger=None) -> None:
    sql = "CREATE TABLE IF NOT EXISTS " + tblName
    sql+= " ("
    sql+= " t TEXT,"
    sql+= " device TEXT,"
    sql+= " latitude REAL,"
    sql+= " longitude REAL,"
    sql+= " battery TEXT,"
    sql+= " PRIMARY KEY(t, device)"
    sql+= " );"
    cur.execute(sql)
    if logger is not None: logging.info("Created table\n%s", sql)

def saveData(cur:sqlite3.Cursor, tblName:str, data:pd.DataFrame, logger:logging.Logger=None)->None:
    a = data[["DeviceDateTime", "DeviceName", "Latitude", "Longitude", "BatteryStatus"]].to_numpy()
    if logger is not None: logger.info("Saving\n%s", a)
    sql = "INSERT OR REPLACE INTO " + tblName + " VALUES(?,?,?,?,?);"
    cur.executemany(sql, a)
    

def sqlSave(data:pd.DataFrame, dbName:str, tblName:str="fixes", logger:logging.Logger=None) -> bool:
    if (data is None) or (data.size == 0): return False

    with sqlite3.connect(dbName) as db:
        cur = db.cursor()
        cur.execute("BEGIN;")
        mkTable(cur, tblName, logger)
        saveData(cur, tblName, data, logger)
        cur.execute("COMMIT;")
    return True

def fetchData(urlBase:str, daysBack:int=None, dt:int=None, logger:logging.Logger=None) -> bool:
    url = [urlBase]
    if daysBack is not None:
        startDate = datetime.date.today() + datetime.timedelta(days=-daysBack)
        url.append("startDate=" + str(startDate))
    if dt is not None: 
        url.append("numMinutes={:d}".format(math.ceil(dt / 60)))
    url = "&".join(url)
    if logger is not None: logger.info("URL=%s", url)
    with requests.get(url) as response:
        if response.status_code != 200:
            if logger is not None:
                logger.error("response Code %s for %s", response.status_code, url)
            return None
        lines = response.content.decode("UTF-8") # Grab the data
        data = None
        for line in lines.split("\r\n"):
            cols = line.split("\t")
            if data is None: # Header
                data = pd.DataFrame(columns=cols)
            elif len(cols) == data.columns.size:
                for index in range(len(cols)):
                    cols[index] = cols[index].strip() # Strip off leading/trailing white space
                    match = re.match(r'"(.*)"', cols[index])
                    if match is not None: cols[index] = str(match.group(1))
                cols = pd.Series(cols, index=data.columns)
                data = data.append(cols, ignore_index=True)
    return data

parser = argparse.ArgumentParser()
MyLogger.addArgs(parser)
parser.add_argument("--apiKey", type=str, default="8F297487-D139-4B23-8E05-6F53C1F97F0E",
        help="REST API key")
parser.add_argument("--baseURL", type=str,
        default="https://api.pacificgyre.com/api2/getData.aspx?apiKey=",
        help="URL base including apiKey=")
parser.add_argument("--dt", type=int, default=120, help="Seconds between data retrival attempts")
parser.add_argument("--extra", type=int, default=600, help="Seconds extra to look back for data")
parser.add_argument("--daysBack", type=int, default=30,
        help="Number of days into the past to start pulling data for")
parser.add_argument("--db", type=str, required=True, help="Database name")
args = parser.parse_args()

logger = MyLogger.mkLogger(args)
logger.info("args=%s", args)

urlBase = args.baseURL + args.apiKey

sqlSave(fetchData(urlBase, args.daysBack, logger=logger), args.db, logger=logger)

while True:
    logger.info("Sleeping for %s", args.dt)
    time.sleep(args.dt)
    sqlSave(fetchData(urlBase, dt=args.dt+args.extra, logger=logger), args.db, logger=logger)
