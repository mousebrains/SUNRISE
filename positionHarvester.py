#! /usr/bin/python3
#
# Harvest data from the various assets and stick them into an SQLite3 database on
# the local machine. Then they can be harvest quickly to generate tracks for each
# asset.
#
# June-2021, Pat Welch, pat@mousebrains.com

import argparse
import MyLogger
import logging
import MyThread
import queue
import datetime
import time
import math
import sqlite3
import inotify_simple as ins
import re
import glob
import os

def fillQueue(q:queue.Queue, root:str, logger:logging.Logger) -> None:
    files = []
    for fn in glob.glob(os.path.join(root, "*")):
        logger.info("fn %s", fn)
        files.append(fn)
    if files: q.put((time.time(), files))

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

class Writer(MyThread.MyThread):
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.MyThread.__init__(self, "Writer", args, logger)
        self.__queue = queue.Queue()
        logger.info("makeing directory %s", os.path.dirname(args.db))
        if os.path.dirname(args.db):
            os.makedirs(os.path.dirname(args.db), mode=0o775, exist_ok=True)
        logger.info("makeing directory %s", os.path.dirname(args.csv))
        if os.path.dirname(args.csv):
            os.makedirs(os.path.dirname(args.csv), mode=0o775, exist_ok=True)
        self.__mkTable()

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group(description="Writer related options")
        grp.add_argument("--db", type=str, default="/home/pat/logs/positions.db",
                help="SQLite3 database location")
        grp.add_argument("--csv", type=str, default="/home/pat/positions.csv",
                help="CSV filename")

    def put(self, records) -> None:
        self.__queue.put(records)

    def __mkTable(self) -> None:
        sql = "CREATE TABLE IF NOT EXISTS fixes (\n"
        sql+= "  ship TEXT,\n"
        sql+= "  name TEXT,\n"
        sql+= "  t TEXT,\n"
        sql+= "  latitude REAL,\n"
        sql+= "  longitude REAL,\n"
        sql+= "  qCSV BOOL DEFAULT 0,\n"
        sql+= "  PRIMARY KEY(ship,name,t)\n"
        sql+= ");"

        sqlPos = "CREATE TABLE IF NOT EXISTS filepos (\n"
        sqlPos+= "  fn TEXT PRIMARY KEY,\n"
        sqlPos+= "  pos INTEGER\n"
        sqlPos+= ");\n"

        logger.info("Creating table in %s\n%s", self.args.db, sql)
        with sqlite3.connect(self.args.db) as db:
            cur = db.cursor()
            cur.execute("BEGIN;")
            cur.execute(sql)
            cur.execute("CREATE INDEX IF NOT EXISTS fixes_t ON fixes (t,name);")
            cur.execute(sqlPos)
            cur.execute("COMMIT;")

    def __writeRecords(self, db:sqlite3.Connection, sqlSelect:str, sqlq:str):
        fn = self.args.csv
        cur0 = db.cursor()
        cur1 = None
        fp = None
        cur0.execute(sqlSelect)
        for row in cur0:
            if fp is None: # First row
                fp = open(fn, "a")
                cur1 = db.cursor()
                cur1.execute("BEGIN;")
            fp.write(",".join(map(str, row)) + "\n")
            cur1.execute(sqlq, row[0:3])
        if fp is not None:
            cur0.execute("COMMIT;")
            fp.close()

    def getPos(self, fn:str) -> int:
        with sqlite3.connect("file:" + self.args.db + "?mode=ro", uri=True) as db:
            cur = db.cursor()
            cur.execute("SELECT pos FROM filepos WHERE fn=?;", (fn,))
            for row in cur:
                return row[0]
            return 0

    def setPos(self, fn:str, pos:int) -> None:
        try:
            with sqlite3.connect(self.args.db) as db:
                cur = db.cursor()
                cur.execute("INSERT OR REPLACE INTO filepos VALUES(?,?);", (fn, pos)) 
        except:
            pass

    def runIt(self) -> None:
        logger = self.logger
        args = self.args
        q = self.__queue
        logger.info("Starting db %s csv %s", args.db, args.csv)

        sqlFiles = "INSERT OR IGNORE INTO fixes VALUES(?,?,?,?,?,0);"

        columns = ",".join(("t", "name", "latitude", "longitude"))
        sqlCSV0 = "SELECT " + columns + " FROM fixes ORDER BY t,name;"
        sqlCSV1 = "SELECT " + columns + " FROM fixes WHERE qCSV=0 ORDER BY t,name;"
        sqlCSV2 = "UPDATE fixes SET qCSV=1 WHERE ship=? AND t=? AND name=?;"

        if not os.path.isfile(args.csv): # File doesn't exist, so create and populate
            with open(args.csv, "w") as fp:
                fp.write(columns + "\n")
            with sqlite3.connect(args.db) as db:
                cur = db.cursor()
                self.__writeRecords(db, sqlCSV0, sqlCSV2)

        while True:
            rows = q.get()
            q.task_done()
            with sqlite3.connect(args.db) as db:
                cur = db.cursor()
                cur.execute("BEGIN;")
                # To avoid concurrency issues
                for row in rows: 
                    items = [row[0], row[1], row[2]] # ship, name, and time
                    items.append(round(row[3], 6)) # Truncate latitude to 6 digits
                    items.append(round(row[4], 6)) # Truncate longitude to 6 digits
                    cur.execute(sqlFiles, items)
                cur.execute("COMMIT;")
                self.__writeRecords(db, sqlCSV1, sqlCSV2)

class Pelican(MyThread.MyThread):
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger,
            q:Writer, inotify:iNotify) -> None:
        MyThread.MyThread.__init__(self, "Pelican", args, logger)
        self.__queue = q
        self.__iNotify = inotify
        self.__regexp = re.compile(r"(\d{2})/(\d{2})/(\d{4}),(\d{2}):(\d{2}):(00)," \
                + "(\d{4}[.]\d+)([NS]),(\d{5}[.]\d+)([EW]),")

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group()
        grp.add_argument("--pelican", type=str, default="/home/pat/Dropbox/Pelican/MIDAS",
                help="Where Pelican's position data is located")

    def __mkDeg(self, val:str, direction:str) -> float:
        # deg * 100 + minutes -> decimal degrees, this is a positive value initially
        val = float(val)
        degrees = math.floor(val / 100)
        minutes = val - (degrees * 100) # fractional minutes
        degrees += minutes / 60
        if direction in ["W", "S", "w", "s"]: degrees *= -1
        return degrees

    def __processFile(self, fn:str) -> None:
        pos = max(0, self.__queue.getPos(fn) - 200)
        regexp = self.__regexp
        try:
            with open(fn, "r") as fp:
                fp.seek(pos) # Start reading from this position
                records = []
                for line in fp:
                    matches = regexp.match(line)
                    if not matches: continue
                    month = int(matches[1])
                    dom = int(matches[2])
                    year = int(matches[3])
                    hour = int(matches[4])
                    minute = int(matches[5])
                    seconds = int(matches[6])
                    t = datetime.datetime(year, month, dom, hour, minute, seconds)
                    lat = self.__mkDeg(matches[7], matches[8])
                    lon = self.__mkDeg(matches[9], matches[10])
                    logger.info("ts %s lat %s lon %s", t, lat, lon)
                    records.append(("Ships", self.name, t, lat, lon))
                self.__queue.setPos(fn, fp.tell())
                if records: 
                    logger.info("Put %s records", len(records))
                    self.__queue.put(records)
        except:
            self.logger.exception("Error processing %s", fn)

    def runIt(self) -> None:
        logger = self.logger
        qWatch = queue.Queue()
        self.__iNotify.addWatch(self.args.pelican, qWatch)
        logger.info("Starting")
        fillQueue(qWatch, self.args.pelican, logger)
        while True:
            (t, files) = qWatch.get()
            qWatch.task_done()
            for filename in files:
                fn = os.path.basename(filename)
                logger.info("fn %s", fn)
                if re.match("MIDAS_\d+.elg", fn):
                    self.__processFile(filename)

class WaltonSmith(MyThread.MyThread):
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger,
            q:Writer, inotify:iNotify) -> None:
        MyThread.MyThread.__init__(self, "WS", args, logger)
        self.__queue = q
        self.__iNotify = inotify
        self.__regexp = {
                 0: (re.compile(r"^\s*(\d{2})\s*(\w+)\s*$"), ("dom", "month")),
                 1: (re.compile(r"^\s*(\d{4})\s+(\d{2}):(\d{2}):(\d{2})\s*$"),
                     ("year", "hour", "minute", "seconds")),
                35: (re.compile(r"^\s*(\d+)\s+(\d+[.]\d*)\s*$"), ("latDeg", "latMin")),
                36: (re.compile(r"^\s*([NS])\s*$"), ("latDir",)),
                37: (re.compile(r"^\s*(\d+)\s+(\d+[.]\d*)\s*$"), ("lonDeg", "lonMin")),
                38: (re.compile(r"^\s*([EW])\s*$"), ("lonDir",)),
                }

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group()
        grp.add_argument("--waltonsmith", type=str, default="/home/pat/Dropbox/WaltonSmith/FTMET",
                help="Where Walton Smith's position data is located")

    def __mkDeg(self, deg:str, minute:str, direction:str):
        deg = float(deg) + float(minute) / 60
        if direction in ("S", "W", "s", "w"): deg *= -1
        return deg

    def __processFile(self, fn:str) -> None:
        pos = max(0, self.__queue.getPos(fn) - 200) # Position to start reading from
        regexp = self.__regexp
        try:
            with open(fn, "r") as fp:
                fp.seek(pos) # Start reading from this position
                records = []
                for line in fp:
                    fields = line.split("\t")
                    if len(fields) != 65: continue # Not a data record
                    info = {}
                    qFail = False
                    for index in regexp:
                        (reLine, keys) = regexp[index]
                        matches = reLine.match(fields[index])
                        if matches is None:
                            qFail = True
                            break
                        for j in range(len(keys)):
                            info[keys[j]] = matches[j+1]
                    if qFail: 
                        logger.info("Skipping %s", line)
                        continue # Skip this line
                    timestring = " ".join((info["year"], info["month"], info["dom"],
                        info["hour"], info["minute"], info["seconds"]))
                    t = datetime.datetime.strptime(timestring, "%Y %B %d %H %M %S")
                    lat = self.__mkDeg(info["latDeg"], info["latMin"], info["latDir"])
                    lon = self.__mkDeg(info["lonDeg"], info["lonMin"], info["lonDir"])
                    logger.info("t %s lat %s lon %s", t, lat, lon)
                    records.append(("Ships", self.name, t, lat, lon))
                self.__queue.setPos(fn, fp.tell())
                if records:
                    logger.info("Put %s records", len(records))
                    self.__queue.put(records)
        except:
            self.logger.exception("Error processing %s", fn)

    def runIt(self) -> None:
        logger = self.logger
        qWatch = queue.Queue()
        self.__iNotify.addWatch(self.args.waltonsmith, qWatch)
        logger.info("Starting")
        fillQueue(qWatch, self.args.waltonsmith, logger)
        while True:
            (t, files) = qWatch.get()
            logger.info("files %s", files)
            qWatch.task_done()
            for filename in files:
                fn = os.path.basename(filename)
                logger.info("fn %s", fn)
                if re.match("WS21163_Hetland-Full Vdl.dat", fn):
                    self.__processFile(filename)

class Drifter(MyThread.MyThread):
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger,
            q:Writer, inotify:iNotify) -> None:
        MyThread.MyThread.__init__(self, "Drifter", args, logger)
        self.__queue = q
        self.__iNotify = inotify
        self.__regexp = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[.]\d+," \
                + r"(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})," \
                + r"(\d+-\d+)," \
                + r"([+-]?\d+[.]\d+)," \
                + r"([+-]?\d+[.]\d+)")

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group()
        grp.add_argument("--drifter", type=str, default="/home/pat/Dropbox/Shore/Drifter",
                help="Where the drifter files are")

    def __processFile(self, fn:str) -> None:
        pos = max(0, self.__queue.getPos(fn) - 200) # Position to start reading from
        regexp = self.__regexp
        try:
            with open(fn, "r") as fp:
                fp.seek(pos) # Start reading from this position
                records = []
                for line in fp:
                    matches = regexp.match(line)
                    if not matches: continue
                    t = datetime.datetime(
                            int(matches[1]), int(matches[2]), int(matches[3]),
                            int(matches[4]), int(matches[5]), int(matches[6]))
                    name = matches[7]
                    lat = float(matches[8])
                    lon = float(matches[9])
                    logger.info("name %s t %s lat %s lon %s", name, t, lat, lon)
                    records.append(("Drifters", name, t, lat, lon))
                self.__queue.setPos(fn, fp.tell())
                if records:
                    logger.info("Put %s records", len(records))
                    self.__queue.put(records)
        except:
            self.logger.exception("Error processing %s", fn)

    def runIt(self) -> None:
        logger = self.logger
        qWatch = queue.Queue()
        self.__iNotify.addWatch(self.args.drifter, qWatch)
        logger.info("Starting %s", self.args.drifter)
        fillQueue(qWatch, self.args.drifter, logger)
        while True:
            (t, files) = qWatch.get()
            qWatch.task_done()
            for filename in files:
                fn = os.path.basename(filename)
                if fn not in ("carthe.csv", "LiveViewGPS.csv"):
                    logger.info("skipping %s", filename)
                    continue
                logger.info("fn %s", filename)
                self.__processFile(filename)

class WireWalker(MyThread.MyThread):
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger,
            q:Writer, inotify:iNotify) -> None:
        MyThread.MyThread.__init__(self, "WW", args, logger)
        self.__queue = q
        self.__iNotify = inotify
        self.__regexp = re.compile( \
                r"(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})," + \
                r"([A-Za-z0-9 ]+)," + \
                r"([+-]?\d+[.]\d+)," + \
                r"([+-]?\d+[.]\d+)")

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group()
        grp.add_argument("--wirewalker", type=str, default="/home/pat/Dropbox/Shore/WireWalker",
                help="Where the wire walker files are")

    def __processFile(self, fn:str) -> None:
        pos = max(0, self.__queue.getPos(fn) - 200) # Position to start reading from
        self.logger.info("fn %s pos %s", fn, pos)
        regexp = self.__regexp
        try:
            with open(fn, "r") as fp:
                fp.seek(pos) # Start reading from this position
                records = []
                for line in fp:
                    matches = regexp.match(line)
                    self.logger.info("line %s matches %s", line, matches)
                    if not matches: continue
                    t = datetime.datetime(
                            int(matches[1]), int(matches[2]), int(matches[3]),
                            int(matches[4]), int(matches[5]), int(matches[6]))
                    name = matches[7]
                    lat = float(matches[8])
                    lon = float(matches[9])
                    records.append(("WireWalker", name, t, lat, lon))
                self.__queue.setPos(fn, fp.tell())
                if records:
                    logger.info("Put %s records", len(records))
                    self.__queue.put(records)
        except:
            self.logger.exception("Error processing %s", fn)

    def runIt(self) -> None:
        logger = self.logger
        qWatch = queue.Queue()
        self.__iNotify.addWatch(self.args.wirewalker, qWatch)
        logger.info("Starting %s", self.args.wirewalker)
        fillQueue(qWatch, self.args.wirewalker, logger)
        while True:
            (t, files) = qWatch.get()
            qWatch.task_done()
            for filename in files:
                fn = os.path.basename(filename)
                if fn != "wirewalker.csv":
                    logger.info("skipping %s", filename)
                    continue
                self.__processFile(filename)

class AIS(MyThread.MyThread):
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger,
            q:Writer, inotify:iNotify) -> None:
        MyThread.MyThread.__init__(self, "AIS", args, logger)
        self.__queue = q
        self.__iNotify = inotify
        self.__regexp = re.compile(r"^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})," \
                + r"(\d+)," \
                + r"([+-]?\d+[.]\d+)," \
                + r"([+-]?\d+[.]\d+)")

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group()
        grp.add_argument("--ais", type=str, action='append',
                help="Where the AIS files are")

    def __processFile(self, fn:str) -> None:
        pos = max(0, self.__queue.getPos(fn) - 200) # Position to start reading from
        regexp = self.__regexp
        try:
            with open(fn, "r") as fp:
                fp.seek(pos) # Start reading from this position
                records = []
                for line in fp:
                    matches = regexp.match(line)
                    if not matches: continue
                    t = datetime.datetime(
                            int(matches[1]), int(matches[2]), int(matches[3]),
                            int(matches[4]), int(matches[5]), int(matches[6]))
                    name = matches[7]
                    lon = float(matches[8])
                    lat = float(matches[9])
                    logger.info("name %s t %s lat %s lon %s", name, t, lat, lon)
                    records.append(("AIS", name, t, lat, lon))
                self.__queue.setPos(fn, fp.tell())
                if records:
                    logger.info("Put %s records", len(records))
                    self.__queue.put(records)
        except:
            self.logger.exception("Error processing %s", fn)

    def runIt(self) -> None:
        logger = self.logger
        qWatch = queue.Queue()
        if self.args.ais is None:
            self.args.ais = [
                    "/home/pat/Dropbox/Pelican/AIS",
                    "/home/pat/Dropbox/WaltonSmith/AIS",
                    ];

        logger.info("Starting %s", self.args.ais)
        for name in args.ais:
            self.__iNotify.addWatch(name, qWatch)
            fillQueue(qWatch, name, logger)

        while True:
            (t, files) = qWatch.get()
            qWatch.task_done()
            for filename in files:
                fn = os.path.basename(filename)
                if fn != "ais.csv":
                    logger.info("skipping %s", filename)
                    continue
                logger.info("fn %s", filename)
                self.__processFile(filename)

class ASV(MyThread.MyThread):
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger,
            q:Writer, inotify:iNotify) -> None:
        MyThread.MyThread.__init__(self, "ASV", args, logger)
        self.__queue = q
        self.__iNotify = inotify
        self.__regexp = re.compile(r"^\d{2}-\w+-\d{4} \d{2}:\d{2}:\d{2} " \
                + r"UBOX\d{2} -- navinfo -- " \
                + r"(\d{4})/(\d{2})/(\d{2}) (\d{2}):(\d{2}):(\d{2}) UTC -- " \
                + r"LAT ([+-]?\d+[.]\d*) " \
                + r"LON ([+-]?\d+[.]\d*) " \
                + r"HD1")
        self.__reName = re.compile(r"RHIB_status_(GS\d_UBOX\d{2}).txt")

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group()
        grp.add_argument("--asv", type=str, default="/home/pat/Dropbox/WaltonSmith/ASV",
                help="Where the ASV files are")
        grp.add_argument("--asvdt", type=float, default=60,
                help="Time spacing between samples to record")

    def __processFile(self, fn:str, name:str) -> None:
        pos = max(0, self.__queue.getPos(fn) - 200) # Position to start reading from
        regexp = self.__regexp
        dtMin = self.args.asvdt
        try:
            with open(fn, "r") as fp:
                fp.seek(pos) # Start reading from this position
                records = []
                tPrev = None
                for line in fp:
                    matches = regexp.match(line)
                    if not matches: continue
                    t = datetime.datetime(
                            int(matches[1]), int(matches[2]), int(matches[3]),
                            int(matches[4]), int(matches[5]), int(matches[6]))
                    lat = float(matches[7])
                    lon = float(matches[8])
                    if tPrev is not None:
                        dt = (t - tPrev).seconds
                        if dt < dtMin: continue # Skip adding since the same time
                    tPrev = t if tPrev is None else max(tPrev, t) # Don't let it go backwards
                    logger.info("name %s t %s lat %s lon %s", name, t, lat, lon)
                    records.append(("ASVs", name, t, lat, lon))
                self.__queue.setPos(fn, fp.tell())
                if records:
                    logger.info("Put %s records", len(records))
                    self.__queue.put(records)
        except:
            self.logger.exception("Error processing %s", fn)

    def runIt(self) -> None:
        logger = self.logger
        qWatch = queue.Queue()
        self.__iNotify.addWatch(self.args.asv, qWatch)
        logger.info("Starting %s", self.args.asv)
        fillQueue(qWatch, self.args.asv, logger)
        reName = self.__reName
        while True:
            (t, files) = qWatch.get()
            qWatch.task_done()
            for filename in files:
                fn = os.path.basename(filename)
                matches = reName.match(fn)
                if not matches:
                    logger.info("skipping %s", filename)
                    continue
                logger.info("fn %s", filename, matches[1])
                self.__processFile(filename, matches[1])

parser = argparse.ArgumentParser()
MyLogger.addArgs(parser)
Writer.addArgs(parser)
Pelican.addArgs(parser)
WaltonSmith.addArgs(parser)
Drifter.addArgs(parser)
WireWalker.addArgs(parser)
AIS.addArgs(parser)
ASV.addArgs(parser)
args = parser.parse_args()

logger = MyLogger.mkLogger(args)

try:
    threads = []
    threads.append(Writer(args, logger))
    threads.append(iNotify(args, logger))
    threads.append(Pelican(args, logger, threads[0], threads[1]))
    threads.append(WaltonSmith(args, logger, threads[0], threads[1]))
    threads.append(Drifter(args, logger, threads[0], threads[1]))
    threads.append(WireWalker(args, logger, threads[0], threads[1]))
    threads.append(AIS(args, logger, threads[0], threads[1]))
    threads.append(ASV(args, logger, threads[0], threads[1]))

    for thrd in threads:
        thrd.start()

    MyThread.waitForException()
except:
    logger.exception("Unexpected exception")
