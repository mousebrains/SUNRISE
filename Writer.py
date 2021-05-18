#
# Write a Mobile originated message to a database
#
# Feb-2020, Pat Welch, pat@mousebrains.com

import queue
import argparse
import logging
import json
import datetime
import sqlite3
from MyThread import MyThread

def mkTable(cur:sqlite3.Cursor, tblName:str, logger:logging.Logger) -> None:
    sql = "CREATE TABLE IF NOT EXISTS " + tblName
    sql+= " ("
    sql+= " tRecv Real,"
    sql+= " ipAddr TEXT,"
    sql+= " port INTEGER,"
    sql+= " t TEXT,"
    sql+= " device TEXT,"
    sql+= " latitude REAL,"
    sql+= " longitude REAL,"
    sql+= " PRIMARY KEY(t, device)"
    sql+= " );"
    cur.execute(sql)
    if logger is not None: logging.info("Created table\n%s", sql)

class Writer(MyThread):
    ''' Wait on a queue, and write the item to a file '''
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.__init__(self, "Writer", args, logger)
        self.dbName = args.db
        self.tblName = args.tblName
        self.q = queue.Queue()

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group(description="Database writer options")
        grp.add_argument("--tblName", type=str, default="fixes", metavar='fixes',
                help="SQLite3 table name")
        grp.add_argument("--db", type=str, required=True, metavar='filename',
                help="SQLite3 database filename")

    def runIt(self) -> None:
        '''Called on thread start '''
        q = self.q
        logger = self.logger
        sql = "INSERT OR IGNORE INTO " + self.tblName + " VALUES(?,?,?,?,?,?,?);"
        logger.info("Starting SQL\n%s", sql)
        while True: # Loop forever
            (t, addr, msg) = q.get()
            (ipAddr, port) = addr
            with sqlite3.connect(self.dbName) as db:
                cur = db.cursor()
                cur.execute("BEGIN;")
                mkTable(cur, self.tblName, logger)
                for item in json.loads(msg):
                    logger.info("ITEM %s", item)
                    sn = item["serial_number"]
                    lat = item["lat"]
                    lon = item["lng"]
                    ts = datetime.datetime.strptime(item["location_time"], "%Y-%m-%d %H:%M:%S")
                    cur.execute(sql, (t, ipAddr, port, ts, sn, lat, lon))
                    logger.info("ipAddr %s port %s sn %s lat %s lon %s ts %s",
                            ipAddr, port, sn, lat, lon, ts)
                cur.execute("COMMIT;")
            self.q.task_done()
