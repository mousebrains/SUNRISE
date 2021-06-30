#! /usr/bin/python3
#
# Monitor the directory where Pelican's MIDAS files are being updated. When they
# are updated, read in the recent data and store the records into an SQLite3 database.
#
# Any new records are appended to the MIDAS file in the Dropbox folder
#
# June-2021, Pat Welch

import argparse
import MyThread
import MyInotify
import MyLogger
import logging
import time
import glob
import queue
import re
import sqlite3
import datetime
import os.path

class MIDAS(MyThread.MyThread):
    def __init__(self, inotify:MyInotify.MyInotify,
            args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.MyThread.__init__(self, "MIDAS", args, logger)
        self.__inotify = inotify
        self.__reLine = re.compile(r"(Date,Time|\d{2}/\d{2}/\d{4},\d{2}:\d{2}:\d{2}),")
        self.__reDate = re.compile(r"(\d{2})/(\d{2})/(\d{4}),(\d{2}):(\d{2}):(\d{2})")
        
    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group(description="MIDAS copy options")
        grp.add_argument("--db", type=str, metavar="fn.db",
                default="/home/pat/Processed/Pelican/MIDAS.db",
                help="SQLite3 database of all the records harvested from the Pelican")
        grp.add_argument("--src", type=str, metavar="directory",
                default="/mnt/GOM/DATALOG40/EventData/MIDAS",
                help="Where the Pelican is writing records to")
        grp.add_argument("--csv", type=str, metavar="filename",
                default="/home/pat/Dropbox/Pelican/MIDAS/MIDAS_001.elg",
                help="CSV file to append records to")
        grp.add_argument("--delay", type=int, default=10,
                help="Seconds after an inotify event until copying is started")

    def __mkDir(self, fn:str) -> None:
        dirname = os.path.dirname(fn)
        if not dirname or os.path.isdir(dirname): return
        self.logger.info("Making %s", dirname)
        os.makedirs(dirname, mode=0o775, exist_ok=True)

    def __fillQueue(self) -> None: # Populate queue with the existing filenames
        files = set()
        for fn in glob.glob(os.path.join(self.args.src, "*")):
            files.add(fn)
        self.__inotify.queue.put(("INITIAL", time.time(), files))

    def __mkTable(self) -> None:
        sql = "CREATE TABLE IF NOT EXISTS rows (\n"
        sql+= "  t REAL PRIMARY KEY,\n"
        sql+= "  row TEXT,\n"
        sql+= "  qCSV DEFAULT 0\n"
        sql+= ");\n"

        sqlPos = "CREATE TABLE IF NOT EXISTS filepos (\n"
        sqlPos+= "  fn TEXT PRIMARY KEY,\n"
        sqlPos+= "  pos INTEGER\n";
        sqlPos+= ");\n"

        sqlHdr = "CREATE TABLE IF NOT EXISTS header (\n"
        sqlHdr+= "  t REAL PRIMARY KEY,\n"
        sqlHdr+= "  n INTEGER,\n"
        sqlHdr+= "  hdr TEXT\n";
        sqlHdr+= ");\n"

        with sqlite3.connect(self.args.db) as db:
            cur = db.cursor()
            cur.execute("BEGIN;")
            cur.execute(sql)
            cur.execute("CREATE INDEX IF NOT EXISTS rows_qcsv ON rows (qCSV);")
            cur.execute(sqlPos)
            cur.execute(sqlHdr)
            cur.execute("COMMIT;")

    def __getNumberOfFields(self, cur:sqlite3.Connection) -> int:
        cur.execute("SELECT n FROM header ORDER by t desc LIMIT 1;")
        for row in cur:
            return row[0]
        return 0

    def __getPos(self, fn:str, cur:sqlite3.Connection, nBack:int=2*200) -> int:
        # maximum line length I've seen is 183 characters, 2*200 should back us up at least 2 lines
        cur.execute("SELECT pos FROM filepos WHERE fn=?;", (fn,))
        for row in cur:
            return max(0, row[0] - nBack)
        return 0

    def __count(self, cur:sqlite3.Connection, tbl:str) -> int:
        cur.execute("SELECT COUNT(*) FROM " + tbl + ";")
        for row in cur: return row[0]
        return -1

    def __digestFile(self, fn:str, cur:sqlite3.Connection) -> int:
        pos = self.__getPos(fn, cur)
        nFields = self.__getNumberOfFields(cur)
        reLine = self.__reLine
        reDate = self.__reDate
        cnt = 0
        nInitial = self.__count(cur, "rows")
        self.logger.info("Working on %s, pos %s", fn, pos)
        with open(fn, "r") as fp:
            fp.seek(pos)
            cur.execute("BEGIN;")
            for line in fp: # Walk through the lines
                matches = reLine.match(line)
                if not matches: continue
                cnt += 1
                key = matches[1]
                n = len(line.split(","))
                line = line.strip()
                if key == "Date,Time": # Header record
                    cur.execute("INSERT OR REPLACE INTO header VALUES(?,?,?);",
                            (time.time(), n, line))
                    nFields = n
                    continue
                if n != nFields:
                    self.logger.info("Number of fields mismatch, %s != %s\n%s", nFields, n, line)
                    continue
                ts = reDate.match(key)
                t = datetime.datetime(
                        int(ts[3]), int(ts[1]), int(ts[2]),
                        int(ts[4]), int(ts[5]), int(ts[6]),
                        tzinfo=datetime.timezone.utc)
                cur.execute("INSERT OR IGNORE INTO rows (t,row) VALUES(?,?);",
                        (t.timestamp(), line))
            cur.execute("INSERT OR REPLACE INTO filepos VALUES(?,?);", (fn, fp.tell()))
            cur.execute("COMMIT;")
        nFinal = self.__count(cur, "rows")
        delta = cnt if nInitial is None or nFinal is None else (nFinal - nInitial)
        self.logger.info("Tried to insert %s rows actually inserted %s rows", cnt, delta)
        return delta

    def __expelCSV(self, cur:sqlite3.Connection) -> None:
        cnt = 0
        times = []
        fn = self.args.csv
        sql = "SELECT t,row FROM rows"
        if not os.path.exists(fn):
            cur.execute("SELECT hdr FROM header ORDER BY t DESC LIMIT 1;")
            for hdr in cur:
                with open(fn, "w") as fp:
                    fp.write(hdr[0] + "\r\n");
                break
        else: # Already exists, so filter on qCSV
            sql += " WHERE qCSV=0"

        cur.execute(sql + ";")
        fp = None
        for row in cur:
            if fp is None: fp = open(fn, "a")
            times.append(row[0])
            fp.write(row[1] + "\r\n")
            cnt += 1
        if fp is not None:
            fp.close()
            cur.execute("BEGIN;")
            for t in times: cur.execute("UPDATE rows SET qCSV=1 WHERE t=?;", (t,))
            cur.execute("COMMIT;")

        self.logger.info("Added %s rows to %s", cnt, fn)

    def __doit(self, fn:str) -> None:
        with sqlite3.connect(self.args.db) as db:
            cur = db.cursor()
            with open(fn, "r") as fp:
                if self.__digestFile(fn, cur):
                    self.__expelCSV(cur)

    def runIt(self) -> None: # Called by MyThread on thread start
        args = self.args
        logger = self.logger
        inotify = self.__inotify
        q = inotify.queue
        delay = args.delay # Delay after a notification before starting a sync
        logger.info("Starting db=%s src=%s csv=%s delay=%s", args.db, args.src, args.csv, delay)
        inotify.addTree(args.src)
        self.__fillQueue() # Add all the existing files to the queue
        self.__mkDir(args.db)
        self.__mkDir(args.csv)
        self.__mkTable() # Create the SQLite3 database

        dt = None # Timeout
        tMin = None
        toSync = set() # Filenames to sync
        while True:
            now = time.time()
            dt = None if tMin is None else (delay - (now - tMin))
            try:
                logger.debug("dt %s", dt)
                if dt is not None and isinstance(dt, float) and dt < 0.1:
                    dt = 0.1
                (action, t, files) = q.get(timeout=dt)
                if tMin is None:
                    tMin = t
                toSync.update(files) # Add in new files to sync
            except queue.Empty:
                tMin = None
                for fn in toSync:
                    if re.match("MIDAS_\d+.elg", os.path.basename(fn)):
                        try:
                            self.__doit(fn)
                        except:
                            logger.exception("Unable to process %s", fn)
                    else:
                        logger.info("Skipping %s", fn)

parser = argparse.ArgumentParser(description="SUNRISE Cruise syncing")
MyLogger.addArgs(parser)
MIDAS.addArgs(parser)

args = parser.parse_args()

logger = MyLogger.mkLogger(args)

logger.info("args %s", args)

try:
    inotify = MyInotify.MyInotify(args, logger)
    midas = MIDAS(inotify, args, logger)

    inotify.start()
    midas.start()

    MyThread.waitForException() # Wait for any errors from the threads
except:
    logger.exception("Unexpected exception")
