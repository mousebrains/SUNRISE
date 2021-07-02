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
import enum
from functools import total_ordering

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

@total_ordering
class WriterAction(enum.IntEnum):
    Pos = 0
    Records = 1
    CSV = 2
    def __lt__(lhs, rhs): return lhs.value < rhs.value
    def __eq__(lhs, rhs): return lhs.value == rhs.value

class PriorityItem:
    def __init__(self, action:WriterAction, data:tuple):
        self.action = action
        self.data = data

    def __lt__(lhs, rhs): return lhs.action < rhs.action
    def __eq__(lhs, rhs): return lhs.action == rhs.action

class Writer(MyThread.MyThread):
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.MyThread.__init__(self, "Writer", args, logger)
        self.__queue = queue.PriorityQueue()
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
        self.__queue.put(PriorityItem(WriterAction.Records, records))

    def __putCSV(self) -> None:
        self.__queue.put(PriorityItem(WriterAction.CSV, None))

    def setPos(self, fn:str, pos:int) -> None:
        self.__queue.put(PriorityItem(WriterAction.Pos, (fn, pos)))


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

    def __expelCSV(self):
        fn = self.args.csv
        qHdr = not os.path.exists(fn)
        columns = ",".join(("t", "name", "latitude", "longitude"))
        sql = "SELECT ship," + columns + " FROM fixes"
        if not qHdr: sql+= " WHERE qCSV=0"
        sql+= " ORDER by t;"

        records = []
        with sqlite3.connect(self.args.db) as db:
            cur = db.cursor()
            cur.execute(sql)
            for row in cur: 
                records.append((row[0], row[1], row[2],
                    str(round(row[3], 6)), str(round(row[4], 6))))

        if not records:
            self.logger.debug("No CSV records for %s", fn)
            return

        with open(fn, "w" if qHdr else "a") as fp:
            if qHdr: fp.write(columns + "\n")
            for row in records: fp.write(",".join(row[1:]) + "\n")

        with sqlite3.connect(self.args.db) as db:
            cur = db.cursor()
            cur.execute("BEGIN;")
            for row in records:
                cur.execute("UPDATE fixes SET qCSV=1 WHERE ship=? AND t=? AND name=?;", row[:3])
            cur.execute("COMMIT;")

        self.logger.info("Wrote %s records to %s", len(records), fn)

    def __writeRows(self, rows:list) -> bool:
        if not rows: return False
        with sqlite3.connect(self.args.db) as db:
            cur = db.cursor()
            cur.execute("BEGIN;")
            cur.execute("SELECT MAX(rowid) FROM fixes;")
            srowid = cur.fetchone()[0]
            if srowid is None: srowid = 0 # First time

            for row in rows: 
                cur.execute("INSERT OR IGNORE INTO fixes VALUES(?,?,?,?,?,0);", row)
            cur.execute("SELECT MAX(rowid) FROM fixes;")
            nRows = cur.fetchone()[0] - srowid
            cur.execute("COMMIT;")
            self.logger.info("Wrote %s rows to %s", nRows, self.args.db)
        return nRows

    def __savePos(self, fn:str, pos:int) -> None:
        with sqlite3.connect(self.args.db) as db:
            cur = db.cursor()
            cur.execute("BEGIN;")
            cur.execute("INSERT OR REPLACE INTO filepos VALUES(?,?);", (fn, pos))
            cur.execute("COMMIT;")

    def getPos(self, fn:str) -> int:
        try:
            with sqlite3.connect("file:" + self.args.db + "?mode=ro", uri=True) as db:
                cur = db.cursor()
                cur.execute("SELECT pos FROM filepos WHERE fn=?;", (fn,))
                for row in cur: return row[0]
        except:
            self.logger.exception("Error getting position for %s", fn)
        return 0


    def runIt(self) -> None:
        logger = self.logger
        args = self.args
        q = self.__queue
        logger.info("Starting db %s csv %s", args.db, args.csv)

        sqlFiles = "INSERT OR IGNORE INTO fixes VALUES(?,?,?,?,?,0);"

        self.__putCSV()

        while True:
            item = q.get()
            q.task_done()
            if item.action == WriterAction.Pos:
                self.__savePos(item.data[0], item.data[1])
            elif item.action == WriterAction.Records:
                if self.__writeRows(item.data): self.__putCSV()
            elif item.action == WriterAction.CSV:
                self.__expelCSV()

class CommonConsume(MyThread.MyThread):
    def __init__(self, name:str, args:argparse.ArgumentParser, logger:logging.Logger,
            q:Writer, inotify:iNotify, dirName, reLine:str, 
            folderName:str, nBack:int=200) -> None:
        MyThread.MyThread.__init__(self, name, args, logger)
        self.__queue = q
        self.__iNotify = inotify
        self.__directories = [dirName] if isinstance(dirName, str) else dirName
        self.__reLine = re.compile(reLine)
        self.folderName = folderName
        self.__nBack = nBack
        self.vesselName = self.name

    def setVesselName(self, matches:re.Match) -> None:
        pass

    def __getPos(self, fn:str) -> int:
        if not os.path.exists(fn):  # Shouldn't happen
            self.logger.warning("Skipping %s since the file does not exist", fn)
            return None
        try:
            pos = self.__queue.getPos(fn)
            sz = os.stat(fn).st_size
            if pos == sz: # File didn't change size
                self.logger.debug("Skipping %s since the size didn't change", fn)
                return None
            if pos > sz: # File was shortened, shouldn't happen
                self.logger.warning("File shortened, %s %s->%s", fn, pos, sz)
                return 0 # Reread
            return max(0, pos - self.__nBack)
        except:
            self.logger.exception("Error getting position for %s", fn)
            return None

    def __fillQueue(self, root:str, qWatch:queue.Queue) -> None:
        files = []
        for fn in glob.glob(os.path.join(root, "*")):
            files.append(fn)
        if files: qWatch.put((time.time(), files))

    def processRecord(self, line:str) -> None: # Common for Drifter, WW, AIS
        regexp = self.regexp
        matches = regexp.match(line)
        if not matches: return None
        t = datetime.datetime(
                int(matches[1]), int(matches[2]), int(matches[3]),
                int(matches[4]), int(matches[5]), int(matches[6]))
        name = matches[7]
        lat = float(matches[8])
        lon = float(matches[9])
        # logger.info("name %s t %s lat %s lon %s", name, t, lat, lon)
        return (self.folderName, name, t, lat, lon)

    def __processFile(self, fn:str, pos:int) -> None:
        logger.info("Process File %s %s", fn, pos)
        records = []
        with open(fn, "r") as fp:
            fp.seek(pos)
            for line in fp:
                row = self.processRecord(line)
                if row: records.append(row)
            self.__queue.setPos(fn, fp.tell())
        self.__queue.put(records)
        self.logger.info("Read %s records from %s pos %s", len(records), fn, pos)

    def runIt(self) -> None: # Called on thread start
        logger = self.logger
        qWatch = queue.Queue()
        reLine = self.__reLine
        logger.info("Starting %s %s", self.__directories, self.__nBack)
        for name in self.__directories:
            self.__iNotify.addWatch(name, qWatch)
            self.__fillQueue(name, qWatch)

        while True:
            (t, files) = qWatch.get()
            qWatch.task_done()
            for filename in files:
                matches = reLine.match(os.path.basename(filename))
                if not matches:
                    logger.debug("Skipping %s", filename)
                    continue
                self.setVesselName(matches)
                pos = self.__getPos(filename)
                if pos is None: continue
                self.__processFile(filename, pos)

class Pelican(CommonConsume):
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger,
            q:Writer, inotify:iNotify) -> None:
        CommonConsume.__init__(self, "Pelican", args, logger, q, inotify,
                args.pelican, r"MIDAS_\d+.elg$", "Ships")
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

    def processRecord(self, line:str) -> tuple:
        matches = self.__regexp.match(line)
        if not matches: return None
        month = int(matches[1])
        dom = int(matches[2])
        year = int(matches[3])
        hour = int(matches[4])
        minute = int(matches[5])
        seconds = int(matches[6])
        t = datetime.datetime(year, month, dom, hour, minute, seconds)
        lat = self.__mkDeg(matches[7], matches[8])
        lon = self.__mkDeg(matches[9], matches[10])
        return (self.folderName, self.vesselName, t, lat, lon)

class WaltonSmith(CommonConsume):
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger,
            q:Writer, inotify:iNotify) -> None:
        CommonConsume.__init__(self, "WS", args, logger, q, inotify,
                args.waltonsmith, r"WS21163_Hetland-Full Vdl.dat$", "Ships")
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

    def processRecord(self, line:str) -> tuple:
        regexp = self.__regexp
        fields = line.split("\t")
        if len(fields) != 65: return None # Not a data record
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
            return None # Skip this line
        timestring = " ".join((
            info["year"], info["month"], info["dom"],
            info["hour"], info["minute"], info["seconds"]))
        t = datetime.datetime.strptime(timestring, "%Y %B %d %H %M %S")
        lat = self.__mkDeg(info["latDeg"], info["latMin"], info["latDir"])
        lon = self.__mkDeg(info["lonDeg"], info["lonMin"], info["lonDir"])
        return ("Ships", self.name, t, lat, lon)

class Drifter(CommonConsume):
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger,
            q:Writer, inotify:iNotify) -> None:
        CommonConsume.__init__(self, "Drifter", args, logger, q, inotify,
                args.drifter, r"(carthe|LiveViewGPS).csv$", "Drifter")
        self.regexp = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[.]\d+," \
                + r"(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})," \
                + r"(\d+-\d+)," \
                + r"([+-]?\d+[.]\d+)," \
                + r"([+-]?\d+[.]\d+)")

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group()
        grp.add_argument("--drifter", type=str, default="/home/pat/Dropbox/Shore/Drifter",
                help="Where the drifter files are")

class WireWalker(CommonConsume):
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger,
            q:Writer, inotify:iNotify) -> None:
        CommonConsume.__init__(self, "WW", args, logger, q, inotify,
                args.wirewalker, r"wirewalker.csv$", "WireWalker")
        self.regexp = re.compile( \
                r"(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})," + \
                r"([A-Za-z0-9 ]+)," + \
                r"([+-]?\d+[.]\d+)," + \
                r"([+-]?\d+[.]\d+)")

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group()
        grp.add_argument("--wirewalker", type=str, default="/home/pat/Dropbox/Shore/WireWalker",
                help="Where the wire walker files are")

class AIS(CommonConsume):
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger,
            q:Writer, inotify:iNotify) -> None:
        if args.ais is None:
            args.ais = [
                    "/home/pat/Dropbox/Pelican/AIS",
                    "/home/pat/Dropbox/WaltonSmith/AIS",
                    ];
        CommonConsume.__init__(self, "AIS", args, logger, q, inotify,
                args.ais, r"ais.csv$", "AIS")
        self.regexp = re.compile(r"^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})," \
                + r"(\d+)," \
                + r"([+-]?\d+[.]\d+)," \
                + r"([+-]?\d+[.]\d+)")

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group()
        grp.add_argument("--ais", type=str, action='append',
                help="Where the AIS files are")

class ASV(CommonConsume):
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger,
            q:Writer, inotify:iNotify) -> None:
        CommonConsume.__init__(self, "ASV", args, logger, q, inotify,
                args.asv, r"(\w+).nav.csv$", "ASVs")
        self.__regexp = re.compile( \
                r"\s*(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\s*," + \
                r"\s*([+-]?\d+[.]?\d*)\s*," + \
                r"\s*([+-]?\d+[.]?\d*)\s*$")
        self.__seen = {}

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group()
        grp.add_argument("--asv", type=str, default="/home/pat/Processed/ASV",
                help="Where the ASV files are")
        grp.add_argument("--asvdt", type=float, default=60,
                help="Time spacing between samples to record")

    def setVesselName(self, matches:re.Match) -> None:
        self.vesselName = matches[1]

    def processRecord(self, line:str) -> None:
        matches = self.__regexp.match(line)
        if not matches: return None
        key = self.vesselName
        t = datetime.datetime(
                int(matches[1]), int(matches[2]), int(matches[3]),
                int(matches[4]), int(matches[5]), int(matches[6]))

        if (key in self.__seen) and ((t - self.__seen[key]).seconds < self.args.asvdt):
            return None
        self.__seen[key] = t

        lat = float(matches[7])
        lon = float(matches[8])
        return (self.folderName, key, t, lat, lon)

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
