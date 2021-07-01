#! /usr/bin/python3
#
# Read in the ASV files and digest the records,
# store them into an SQLite3 database,
# then append new records to CSV files.
#
# There will be one database table and one CSV per records type.
#
# June-2021, Pat Welch

import argparse
import MyLogger
import logging
import MyThread
import inotify_simple as ins
import sqlite3
import queue
import glob
import os
import datetime
import time
import re

class iNotify(MyThread.MyThread):
    # Modified version of MyInotify.py
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger):
        MyThread.MyThread.__init__(self, "INotify", args, logger)
        self.__mapping = {}
        self.__inotify = ins.INotify()
        self.__flags = ins.flags.CLOSE_WRITE | ins.flags.MOVED_TO
    
    def __repr__(self) -> str:
        items = []
        for key in self.__mapping:
            items.append("{} -> {}".format(key, self.__mapping[key]))
        return "\n".join(items)

    def addWatch(self, dirName:str, q:queue.Queue) -> None:
        wd = self.__inotify.add_watch(dirName, self.__flags)
        self.__mapping[wd] = [dirName, q]
        self.logger.debug("add %s %s %s", wd, dirName, q)

    def runIt(self) -> None: # Called on thread start
        inotify = self.__inotify
        items = self.__mapping
        logger = self.logger
        logger.info("Starting")
        while True:
            events = inotify.read()
            t0 = time.time()
            files = set()
            try:
                mapping = {}
                for event in events:
                    wd = event.wd
                    if (wd not in items):
                        if not (event.mask & ins.flags.IGNORED):
                            logger.warning("Missing wd for %s", event)
                        continue
                    if event.name == "": continue # Skip updates to the directory itself
                    info = items[wd]
                    fn = os.path.join(info[0], event.name)
                    q = info[1]
                    if q not in mapping: mapping[q] = set()
                    mapping[q].add(fn)
                if mapping: 
                    for q in mapping:
                        q.put((t0, mapping[q]))
            except:
                logger.exception("GotMe")

class Regurgitate(MyThread.MyThread):
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger, inotify:iNotify):
        MyThread.MyThread.__init__(self, "EAT", args, logger)
        self.__queue = queue.Queue()
        self.__inotify = inotify
        self.__reLine = re.compile(
                r"^\d{2}-\w+-\d{4} \d{2}:\d{2}:\d{2} UBOX\d{2} -- " +
                r"(adcp|keelctd|navinfo) -- " +
                r"(\d{4})/(\d{2})/(\d{2}) (\d{2}):(\d{2}):(\d{2}) UTC -- " +
                r"(.*)$")
        self.__reCTD = re.compile(
                r"KDATE \d{4}-\d{2}-\d{2} KTIME \d{2}:\d{2}:\d{2}[.]\d{3} " +
                r"Temp\s+([+-]?\d+[.]\d{4})\s*"
                r"Sal\s+([+-]?\d+[.]\d{4})\s*")
        velFmt = r"([+-]?\d+)"
        self.__reADCP = re.compile(
                r"ADATE \d{8} ATIME \d{6}" +
                r" u " + velFmt +
                r" v " + velFmt +
                r" w " + velFmt +
                r"$")
        self.__reNAV = re.compile(
                r"LAT ([+-]?\d+[.]\d*) "
                r"LON ([+-]?\d+[.]\d*) "
                r"HD1")


    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        parser.add_argument("--dir", type=str, required=True,
                help="Directory to monitor for file changes")
        parser.add_argument("--db", type=str, required=True, help="SQLite3 database name")
        parser.add_argument("--csv", type=str, required=True,
                help="Directory to write CSV files to")

    def __makeDir(self, dirname:str) -> None:
        if dirname and not os.path.isdir(dirname):
            self.logger.info("Making %s", dirname)
            os.makedirs(dirname, mode=0o775, exist_ok=True)

    def __fillQueue(self, q:queue.Queue, root:str) -> None:
        files = []
        for fn in glob.glob(os.path.join(root, "*")):
            files.append(fn)
        if files:
            q.put((time.time(), files))

    def __makeTable(self):
        logger = self.logger
        args = self.args

        sqlNav = "CREATE TABLE IF NOT EXISTS nav (\n"
        sqlNav+= "  boat TEXT,\n"
        sqlNav+= "  t TEXT,\n"
        sqlNav+= "  latitude REAL,\n"
        sqlNav+= "  longitude REAL,\n"
        sqlNav+= "  qCSV BOOL DEFAULT 0,\n"
        sqlNav+= "  PRIMARY KEY(boat, t)\n"
        sqlNav+= ");\n"

        sqlADCP = "CREATE TABLE IF NOT EXISTS adcp (\n"
        sqlADCP+= "  boat TEXT,\n"
        sqlADCP+= "  t TEXT,\n"
        sqlADCP+= "  u REAL,\n"
        sqlADCP+= "  v REAL,\n"
        sqlADCP+= "  w REAL,\n"
        sqlADCP+= "  qCSV BOOL DEFAULT 0,\n"
        sqlADCP+= "  PRIMARY KEY(boat, t)\n"
        sqlADCP+= ");\n"
 
        sqlCTD = "CREATE TABLE IF NOT EXISTS ctd (\n"
        sqlCTD+= "  boat TEXT,\n"
        sqlCTD+= "  t TEXT,\n"
        sqlCTD+= "  temperature REAL,\n"
        sqlCTD+= "  salinity REAL,\n"
        sqlCTD+= "  qCSV BOOL DEFAULT 0,\n"
        sqlCTD+= "  PRIMARY KEY(boat, t)\n"
        sqlCTD+= ");\n"

        sqlPos = "CREATE TABLE IF NOT EXISTS filePos (\n"
        sqlPos+= "  fn TEXT PRIMARY KEY,\n"
        sqlPos+= "  pos INTEGER\n"
        sqlPos+= ");\n"
 
        with sqlite3.connect(args.db) as db:
            cur = db.cursor()
            cur.execute("BEGIN;")
            cur.execute("PRAGMA journal_mode=wal2;")
            cur.execute(sqlNav)
            cur.execute("CREATE INDEX IF NOT EXISTS nav_qcsv ON nav (qCSV);")
            cur.execute(sqlADCP)
            cur.execute("CREATE INDEX IF NOT EXISTS adcp_qcsv ON adcp (qCSV);")
            cur.execute(sqlCTD)
            cur.execute("CREATE INDEX IF NOT EXISTS ctd_qcsv ON ctd (qCSV);")
            cur.execute(sqlPos)
            cur.execute("COMMIT;")

    def __getPos(self, fn:str) -> int:
        try:
            sz = os.stat(fn).st_size
        except:
            return None # File does not exist

        with sqlite3.connect(args.db) as db:
            cur = db.cursor()
            cur.execute("SELECT pos FROM filePos WHERE fn=?;", (fn,))
            for row in cur:
                pos = row[0]
                if pos == sz: return None # Same place, so do nothing
                return max(0, pos - 200)
        return 0

    def __navinfo(self, boat:str, t:datetime.datetime, body:str) -> tuple:
        matches = self.__reNAV.match(body)
        if not matches: return None
        lat = float(matches[1])
        lon = float(matches[2])
        return (boat, t, lat, lon)

    def __keelctd(self, boat:str, t:datetime.datetime, body:str) -> tuple:
        matches = self.__reCTD.match(body)
        if not matches: return None
        temp = float(matches[1])
        sal = float(matches[2])
        if temp == 0: return None
        return (boat, t, temp, sal)

    def __adcp(self, boat:str, t:datetime.datetime, body:str) -> tuple:
        matches = self.__reADCP.match(body)
        if not matches: return None
        u = float(matches[1])
        v = float(matches[2])
        w = float(matches[3])
        if u == 0 and v == 0 and w == 0: return None
        return (boat, t, u, v, w)

    def __processFile(self, fn:str, boat:str) -> bool:
        logger = self.logger
        args = self.args
        reLine = self.__reLine

        pos = self.__getPos(fn)
        if pos is None: return # Nothing new to look at here

        records = {"nav": [], "ctd": [], "adcp": []}
        with open(fn, "r") as fp:
            fp.seek(pos)
            for line in fp:
                matches = reLine.match(line)
                if not matches: continue # Not a match
                action = matches[1]
                t = datetime.datetime(
                        int(matches[2]), int(matches[3]), int(matches[4]),
                        int(matches[5]), int(matches[6]), int(matches[7]))
                body = matches[8]
                if action == "navinfo":
                    row = self.__navinfo(boat, t, body)
                    if row is not None: records["nav"].append(row)
                elif action == "keelctd":
                    row = self.__keelctd(boat, t, body)
                    if row is not None: records["ctd"].append(row)
                elif action == "adcp":
                    row = self.__adcp(boat, t, body)
                    if row is not None: records["adcp"].append(row)
                else:
                    logger.warning("Unsupported action %s\n%s", action, line)
            with sqlite3.connect(self.args.db) as db:
                cur = db.cursor()
                cur.execute("BEGIN;")
                cur.execute("INSERT OR REPLACE INTO filePos VALUES(?,?);", (fn, fp.tell()))
                cur.execute("COMMIT;")

        cnts = {
                "nav": len(records["nav"]), 
                "ctd": len(records["ctd"]), 
                "adcp": len(records["adcp"]),
                }

        if not cnts["nav"] and not cnts["ctd"] and not cnts["adcp"]: return False

        with sqlite3.connect(self.args.db) as db:
            cur = db.cursor()
            cur.execute("BEGIN;")
            for row in records["nav"]:
                cur.execute("INSERT OR IGNORE INTO nav VALUES (?,?,?,?,0);", row)
            for row in records["ctd"]:
                cur.execute("INSERT OR IGNORE INTO ctd VALUES (?,?,?,?,0);", row)
            for row in records["adcp"]:
                cur.execute("INSERT OR IGNORE INTO ctd VALUES (?,?,?,?,?,0);", row)
            cur.execute("COMMIT;")
        logger.info("Processed %s", fn)
        logger.info("Starting at %s boat %s counts %s", pos, boat, cnts)
        return True

    def __processCSVTable(self, boat:str, tbl:str, columns:tuple[str], rnd:int) -> None:
        logger = self.logger
        fn = os.path.join(self.args.csv, boat + "." + tbl + ".csv")
        qHdr = not os.path.exists(fn)
        columns = ",".join(columns)
        sql = "SELECT " + columns + " FROM " + tbl
        if os.path.exists(fn): sql += " WHERE qCSV=1"
        sql += " ORDER BY t;"

        records = []
        with sqlite3.connect(args.db) as db:
            cur = db.cursor()
            cur.execute(sql)
            for row in cur: records.append(row)

        if not records: return

        with open(fn, "w" if qHdr else "a") as fp:
            if qHdr:
                fp.write(columns + "\n")
            for row in records: 
                if rnd is not None:
                    a = [row[0]]
                    for i in range(1, len(row)): a.append(round(row[i], rnd))
                    row = a
                fp.write(",".join(map(str, row)) + "\n")

        sql = "UPDATE " + tbl + " SET qCSV=1 WHERE boat=? AND t=?;"
        with sqlite3.connect(args.db) as db:
            cur = db.cursor()
            cur.execute("BEGIN;")
            for row in records: cur.execute(sql, (boat, row[0]))
            cur.execute("COMMIT;")

        self.logger.info("Wrote %s records to %s for %s", len(records), tbl, boat)

    def __processCSV(self, boat:str) -> None:
        self.__processCSVTable(boat, "nav", ("t", "latitude", "longitude"), 6)
        self.__processCSVTable(boat, "ctd", ("t", "temperature", "salinity"), None)
        self.__processCSVTable(boat, "adcp", ("t", "u", "v", "w"), None)

    def runIt(self) -> None: # Called on thread start
        logger = self.logger
        args = self.args
        qWatch = queue.Queue()
        logger.info("Starting %s %s %s", args.dir, args.db, args.csv)

        self.__makeDir(args.dir)
        self.__makeDir(args.csv)
        self.__makeDir(os.path.dirname(args.db))

        self.__makeTable()

        self.__inotify.addWatch(args.dir, qWatch)
        self.__fillQueue(qWatch, args.dir)
        reFile = re.compile(r"^.*/RHIB_status_GS\d_UBOX\d{2}_(\w+)_\d{8}_\d{6}.txt$")
        while True:
            (t, files) = qWatch.get()
            qWatch.task_done()
            for filename in files:
                matches = reFile.match(filename)
                if not matches:
                    logger.info("Skipping %s", filename)
                    continue
                boat = matches[1]
                if self.__processFile(filename, boat):
                    self.__processCSV(boat)

parser = argparse.ArgumentParser()
MyLogger.addArgs(parser)
Regurgitate.addArgs(parser)
args = parser.parse_args()

logger = MyLogger.mkLogger(args)

try:
    threads = []
    threads.append(iNotify(args, logger))
    threads.append(Regurgitate(args, logger, threads[0]))

    for thrd in threads:
        thrd.start()

    MyThread.waitForException()
except:
    logger.exception("Unexpected exception args=%s", args)
