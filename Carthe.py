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
import io
import os.path

class Fetcher:
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        self.args = args
        self.logger = logger
        self.tPrev = time.time()

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group(description="Fetcher options")
        grp.add_argument("--apiKey", type=str, default="8F297487-D139-4B23-8E05-6F53C1F97F0E",
                help="REST API key")
        grp.add_argument("--baseURL", type=str,
                default="https://api.pacificgyre.com/api2/getData.aspx?apiKey=",
                help="URL base including apiKey=")
        grp.add_argument("--extra", type=int, default=600,
                help="Seconds extra to look back for data")
        grp.add_argument("--daysBack", type=int,
                help="Number of days into the past to start pulling data for")

    def fetch(self, daysBack:int=None) -> pd.DataFrame:
        args = self.args
        logger = self.logger
        urlBase = [args.baseURL + args.apiKey]
        daysBack = daysBack if daysBack is not None else args.daysBack
        dt = args.extra
        url = [args.baseURL + args.apiKey]
        if daysBack is not None:
            startDate = datetime.date.today() + datetime.timedelta(days=-daysBack)
            url.append("startDate=" + str(startDate))
        elif dt is not None:
            url.append("numMinutes={:d}".format(math.ceil(dt / 60)))
        url = "&".join(url)
        logger.info("URL=%s", url)
        with requests.get(url) as response:
            t0 = datetime.datetime.now(tz=datetime.timezone.utc) # Timestamp for this fetch
            if response.status_code != 200:
                logger.error("response Code %s for %s", response.status_code, url)
                return None
            f = io.StringIO(response.content.decode("UTF-8")) # Grab the data
            df = pd.read_csv(f, delimiter="\t", header=0)
            df["tRecv"] = t0.strftime("%Y-%m-%d %H:%M:%S.%f")
            return df

class DBupdater:
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        self.args = args
        self.logger = logger

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group(description="Database related options")
        grp.add_argument("--db", type=str, default="Carthe.db", help="Database name")
        grp.add_argument("--table", type=str, default="fixes", help="Table name in database")

    def save(self, data:pd.DataFrame) -> None:
        if data is None: return
        logger = self.logger
        with sqlite3.connect(self.args.db) as db:
            cur = db.cursor()
            cur.execute("BEGIN;")
            self.mkTable(cur)
            self.saveData(cur, data)
            cur.execute("COMMIT;")

    def mkTable(self, cur:sqlite3.Cursor) -> None:
        sql = "CREATE TABLE IF NOT EXISTS " + self.args.table + " (\n"
        sql+= " tRecv TEXT,\n"
        sql+= " t TEXT,\n"
        sql+= " device TEXT,\n"
        sql+= " latitude REAL,\n"
        sql+= " longitude REAL,\n"
        sql+= " battery TEXT,\n"
        sql+= " qCSV BOOL DEFAULT 0,\n"
        sql+= " PRIMARY KEY(t, device)\n"
        sql+= " );"
        cur.execute(sql)
        sql = "CREATE INDEX IF NOT EXISTS " + self.args.table + \
                "_{} ON " + self.args.table + " ({});"
        cur.execute(sql.format("tRecv", "tRecv"))
        cur.execute(sql.format("qCSV", "qCSV"))
        logging.info("Created table\n%s", sql)

    def saveData(self, cur:sqlite3.Cursor, df:pd.DataFrame) -> None:
        sql = "INSERT OR IGNORE INTO " + self.args.table + " VALUES(?,?,?,?,?,?,0);"
        for index in range(df.shape[0]):
            row = df.iloc[index]
            cur.execute(sql, (
                row.tRecv, row.DeviceDateTime, row.DeviceName, 
                row.Latitude, row.Longitude, row.BatteryStatus))

class CSV:
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        self.args = args
        self.logger = logger
        self.tPrev = 0

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group(description="CSV related options")
        grp.add_argument("--csv", type=str, help="CSV filename")

    def save(self) -> None:
        args = self.args

        if args.csv is None:  # Skip CSV generation
            return

        columns = ("tRecv", "t", "device", "latitude", "longitude", "battery")
        sql = "SELECT " + ",".join(columns) + " FROM " + args.table
        qHeader = not os.path.isfile(args.csv)
        if not qHeader: # File already exists
            sql+= " WHERE qCSV=0"
        sql+= " ORDER BY t;"

        sqlq = "UPDATE " + args.table + " SET qCSV=1"
        sqlq+= " WHERE t=? AND device=?;"

        with sqlite3.connect(args.db) as db:
            cur0 = db.cursor()
            cur1 = None
            fp = None
            cur0.execute(sql)
            for row in cur0:
                (t, device) = row[1:3]
                if fp is None:
                    cur1 = db.cursor()
                    if qHeader:
                        fp = open(args.csv, "w")
                        fp.write(",".join(columns) + "\n")
                    else:
                        fp = open(args.csv, "a")
                fp.write(",".join(map(str, row)) + "\n")
                cur1.execute(sqlq, (t, device))
            if fp is not None:
                fp.close()
        
parser = argparse.ArgumentParser()
MyLogger.addArgs(parser)
Fetcher.addArgs(parser)
DBupdater.addArgs(parser)
CSV.addArgs(parser)
parser.add_argument("--dt", type=int, default=120, metavar="seconds",
        help="Seconds between data retrival attempts")
args = parser.parse_args()

logger = MyLogger.mkLogger(args)
logger.info("args=%s", args)

try:
    fetcher = Fetcher(args, logger)
    updater = DBupdater(args, logger)
    csv = CSV(args, logger)

    data = fetcher.fetch(daysBack=args.daysBack) # Get last 120 days worth of data
    updater.save(data)
    csv.save()
    # sqlSave(fetchData(urlBase, args.daysBack, logger=logger), args.db, logger=logger)
    tPrev = time.time()
    while True:
        now = time.time()
        dt = args.dt - (now - tPrev)
        if dt < 0.1:
            data = fetcher.fetch()
            updater.save(data)
            csv.save()
            tPrev = time.time()
            dt = args.dt - (tPrev - now)
        else:
            tPrev = now
        logger.info("Sleeping for %s seconds", dt)
        time.sleep(dt)
except:
    logger.exception("Unexpected exception")
