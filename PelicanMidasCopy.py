#! /usr/bin/python3
#
# Monitor the directory where Pelican's MIDAS files are being updated. When they
# are updated, read in the recent data and store the records into an SQLite3 database.
#
# Any new records are appended to the MIDAS file in the Dropbox folder
#
# June-2021, Pat Welch

import argparse
import MyLogger
import logging
import time
import glob
import queue
import re
import sqlite3
import datetime
import os.path

class MIDAS:
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        self.args = args
        self.logger = logger
        self.__reLine = re.compile(r"(Date,Time|\d{2}/\d{2}/\d{4},\d{2}:\d{2}:\d{2}),")
        self.__reDate = re.compile(r"(\d{2})/(\d{2})/(\d{4}),(\d{2}):(\d{2}):(\d{2})")
        self.__mkDir(args.db)
        self.__mkDir(args.csv)
        self.__mkTable()
        
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

    def __mkDir(self, fn:str) -> None:
        dirname = os.path.dirname(fn)
        if not dirname or os.path.isdir(dirname): return
        self.logger.info("Making %s", dirname)
        os.makedirs(dirname, mode=0o775, exist_ok=True)

    def run(self) -> None: # Populate queue with the existing filenames
        for fn in glob.glob(os.path.join(self.args.src, "*")):
            if re.match("MIDAS_\d+.elg", os.path.basename(fn)):
                self.__doit(fn)

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

parser = argparse.ArgumentParser(description="SUNRISE Cruise syncing of Pelican MIDAS data")
MyLogger.addArgs(parser)
MIDAS.addArgs(parser)
# Since we don't get inotify events for MIDAS_*.elg periodically check it
parser.add_argument("--delay", type=float, default=300, help="Seconds between directoy scans")
args = parser.parse_args()

logger = MyLogger.mkLogger(args)

logger.info("args %s", args)

midas = MIDAS(args, logger)

while True:
    try:
        midas.run()
    except:
        logger.exception("Midas failed")
    logger.info("Sleeping for %s seconds", args.delay)
    time.sleep(args.delay)
