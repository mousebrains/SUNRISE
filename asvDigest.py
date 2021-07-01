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
            os.makedirs(dirname, mode=0o775, exists_ok=True)

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

    def __getPos(self, cur:sqlite3.Cursor, fn:str) -> int:
        cur.execute("SELECT pos FROM filePos WHERE fn=?;", (fn,))
        for row in cur:
            pos = row[0]
            try:
                sz = os.stat(fn).st_size
                if pos == sz: return None
                return max(0, pos - 200)
            except:
                return 0
        return 0

    def __navinfo(self, cur:sqlite3.Cursor, boat:str, t:datetime.datetime, body:str) -> bool:
        matches = self.__reNAV.match(body)
        if not matches: return False
        lat = float(matches[1])
        lon = float(matches[2])
        cur.execute("INSERT OR IGNORE INTO nav VALUES(?,?,?,?,0);", (boat, t, lat, lon))
        return True

    def __keelctd(self, cur:sqlite3.Cursor, boat:str, t:datetime.datetime, body:str) -> bool:
        matches = self.__reCTD.match(body)
        if not matches: return False
        temp = float(matches[1])
        sal = float(matches[2])
        if temp != 0:
            cur.execute("INSERT OR IGNORE INTO ctd VALUES(?,?,?,?,0);", (boat, t, temp, sal))
            return True
        return False

    def __adcp(self, cur:sqlite3.Cursor, boat:str, t:datetime.datetime, body:str) -> bool:
        matches = self.__reADCP.match(body)
        if not matches: return False
        u = float(matches[1])
        v = float(matches[2])
        w = float(matches[3])
        if u != 0 or v != 0 or w != 0:
            cur.execute("INSERT OR IGNORE INTO adcp VALUES(?,?,?,?,?,0);", (boat, t, u, v, w))
            return True
        return False

    def __processFile(self, cur:sqlite3.Cursor, fn:str, boat:str) -> bool:
        logger = self.logger
        args = self.args
        reLine = self.__reLine

        pos = self.__getPos(cur, fn)
        if pos is None: return # Nothing new to look at here

        counts = {}
        qReturn = False
        with open(fn, "r") as fp:
            fp.seek(pos)
            cur.execute("BEGIN;")
            for line in fp:
                matches = reLine.match(line)
                if not matches: continue # Not a match
                action = matches[1]
                t = datetime.datetime(
                        int(matches[2]), int(matches[3]), int(matches[4]),
                        int(matches[5]), int(matches[6]), int(matches[7]))
                body = matches[8]
                if action not in counts: counts[action] = 0
                counts[action] += 1
                if action == "navinfo":
                    qReturn |= self.__navinfo(cur, boat, t, body)
                elif action == "keelctd":
                    qReturn |= self.__keelctd(cur, boat, t, body)
                elif action == "adcp":
                    qReturn |= self.__adcp(cur, boat, t, body)
                else:
                    logger.warning("Unsupported action %s\n%s", action, line)
            cur.execute("INSERT OR REPLACE INTO filePos VALUES(?,?);", (fn, fp.tell()))
            cur.execute("COMMIT;")
        logger.info("Processed %s", fn)
        logger.info("Starting at %s boat %s counts %s", pos, boat, counts)
        return qReturn

    def __processCSV(self, db:sqlite3.Connection, cur:sqlite3.Cursor, boat:str) -> None:
        logger = self.logger
        prefix = os.path.join(self.args.csv, boat)
        tables = {
                "nav":  {"columns": ["t", "latitude", "longitude"], "round": 6},
                "ctd":  {"columns": ["t", "temperature", "salinity"]},
                "adcp": {"columns": ["t", "u", "v", "w"]},
                }
        logger.info("CSV %s", boat)
        cur1 = None
        for tbl in tables: # Walk through tables looking for new entries
            columns = ",".join(tables[tbl]["columns"])
            fn = prefix + "." + tbl + ".csv"
            sql = "SELECT " + columns + " FROM " + tbl
            sqlCSV = "UPDATE " + tbl + " SET qCSV=1 WHERE boat=? AND t=?;"
            fp = None
            if not os.path.exists(fn):
                fp = open(fn, "w")
                fp.write(columns + "\n")
            else:
                sql += " WHERE qCSV=0"
            sql += " ORDER BY t desc;"

            cur.execute(sql) # Fetch rows to output
            records = []
            rnd = tables[tbl]["round"] if "round" in tables[tbl] else None
            cnt = 0
            for row in cur:
                if fp is None: fp = open(fn, "a")
                if rnd is not None:
                    a = [row[0]]
                    for i in range(1, len(row)):
                        a.append(round(row[i], rnd))
                    row = a
                fp.write(",".join(map(str, row)) + "\n")
                if cur1 is None:
                    cur1 = db.cursor()
                    cur1.execute("BEGIN;")
                cur1.execute(sqlCSV, (boat, row[0]))
                cnt += 1

            if fp is not None: 
                fp.close()
                fp = None
            if cnt > 0: 
                logger.info("Wrote tbl %s -> %s records to %s", tbl, cnt, fn)
        if cur1 is not None:
            cur1.execute("COMMIT;")

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
                with sqlite3.connect(args.db) as db:
                    cur = db.cursor()
                    if self.__processFile(cur, filename, boat):
                        self.__processCSV(db, cur, boat)

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
