#! /usr/bin/env python3
#
# Listen to a socket for a datagram with status information about my computers on the ship
#
# May-2021, Pat Welch, pat@mousebrains.com

import queue
import sqlite3
import socket
import threading
import time
import MyLogger
import logging
import argparse
import json
import os.path
from MyThread import MyThread,waitForException

class Reader(MyThread):
    ''' Wait for a datagram, then send that to the Writer via a queue '''
    def __init__(self, queue:queue.Queue,
            args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.__init__(self, "Reader", args, logger)
        self.__queue = queue

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group(description="UDP Listener options")
        grp.add_argument('--port', type=int, default=11113, metavar='port',
                help='Port to listen on')
        grp.add_argument("--size", type=int, default=65536, help="Datagram size")

    def runIt(self) -> None:
        '''Called on thread start '''
        args = self.args
        q = self.__queue
        logger = self.logger
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            logger.debug("Opened UDP socket")
            s.bind(('', args.port))
            logger.info('Bound to port %s', args.port)
            while True: # Read datagrams
                (data, senderAddr) = s.recvfrom(args.size)
                t = time.time()
                logger.info("Received from %s n %s", senderAddr, len(data))
                q.put((t, senderAddr, data))

class Writer(MyThread):
    ''' Wait on a queue, and write the item to a database '''
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.__init__(self, "Writer", args, logger)
        self.qIn = queue.Queue()
        self.qOut = queue.Queue()

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group(description="Database writer options")
        grp.add_argument("--tOffset", type=int, default=1622346500,
                help="Subtracted from current time before being sent")
        grp.add_argument("--tempNorm", type=float, default=100,
                help="divide received temperature by this to get degrees C")
        grp.add_argument("--spaceNorm", type=float, default=100,
                help="divide received used/free by this to get degrees GB")
        grp.add_argument("--table", type=str, default="status", metavar="status",
                help="SQLite3 table name")
        grp.add_argument("--db", type=str, required=True, metavar='filename',
                help="SQLite3 database filename")

    def mkTable(self, cur:sqlite3.Cursor) -> None:
        tbl = self.args.table
        sql = "CREATE TABLE IF NOT EXISTS " + tbl + "(\n"
        sql+= " tRecv Real,\n"
        sql+= " ipAddr TEXT,\n"
        sql+= " port INTEGER,\n"
        sql+= " t REAL,\n"
        sql+= " host TEXT,\n"
        sql+= " temp REAL,\n"
        sql+= " used REAL,\n"
        sql+= " free REAL,\n"
        sql+= " qCSV BOOL DEFAULT 0,\n"
        sql+= " PRIMARY KEY(t, host)\n"
        sql+= " );"
        cur.execute(sql)
        cur.execute("CREATE INDEX IF NOT EXISTS " + tbl + "_qCSV ON " + tbl + " (qCSV);")

    def parseMsg(self, msg:bytes) -> dict:
        args = self.args
        if len(msg) < 14: return None
        hdr = int.from_bytes(msg[0:2], byteorder="big", signed=False)
        if hdr != 0x0123: return None
        info = {}
        info["t"] = int.from_bytes(msg[2:6], byteorder="big", signed=False) + args.tOffset
        info["temp"] = int.from_bytes(msg[6:8], byteorder="big", signed=True) / args.tempNorm
        info["free"] = int.from_bytes(msg[8:10], byteorder="big", signed=False) / args.spaceNorm
        info["used"] = int.from_bytes(msg[10:12], byteorder="big", signed=False) / args.spaceNorm
        n = int.from_bytes(msg[12:14], byteorder="big", signed=False)
        if len(msg) != (n + 14): return None
        try:
            info["host"] = str(msg[14:], "utf-8")
        except:
            return None

        return info

    def runIt(self) -> None:
        '''Called on thread start '''
        qIn = self.qIn
        qOut = self.qOut
        logger = self.logger
        sql = "INSERT OR IGNORE INTO " + self.args.table + " VALUES(?,?,?,?,?,?,?,?,0);"
        logger.info("Starting SQL\n%s", sql)
        while True: # Loop forever
            (t, addr, msg) = qIn.get()
            (ipAddr, port) = addr
            info = self.parseMsg(msg)
            if info is None: continue
            row = [t, ipAddr, port,
                    info["t"], info["host"], info["temp"], info["used"], info["free"]]
            logger.info("Received %s %s temp %s used %s free %s",
                    info["host"], info["t"], info["temp"], info["used"], info["free"])
            with sqlite3.connect(self.args.db) as db:
                cur = db.cursor()
                cur.execute("BEGIN;")
                self.mkTable(cur)
                cur.execute(sql, row)
                cur.execute("COMMIT;")
            qIn.task_done()
            qOut.put(True)

class CSV(MyThread):
    ''' Wait on a queue to look at a database and update a CSV file '''
    def __init__(self, q:queue.Queue, args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.__init__(self, "CSV", args, logger)
        self.__queue = q

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        parser.add_argument("--csv", type=str, help="CSV filename")

    def runIt(self) -> None: # Called on thread start
        q = self.__queue
        args = self.args
        logger = self.logger
        logger.info("Starting")
        qHeader = True if args.csv is None else not os.path.isfile(args.csv)
        columns = ("tRecv", "t", "host", "temp", "used", "free")
        sql0 = "SELECT " + ",".join(columns) + " FROM " + args.table + " WHERE qCSV=0 ORDER BY t;"
        sql1 = "SELECT " + ",".join(columns) + " FROM " + args.table + " ORDER BY t;"
        sqlq = "UPDATE " + args.table + " SET qCSV=1  WHERE t=? AND host=?;"

        while True:
            msg = q.get()
            q.task_done()
            if args.csv is None:
                continue # Nothing to do
            with sqlite3.connect(args.db) as db:
                cur0 = db.cursor()
                cur1 = None
                fp = None
                cur0.execute(sql1 if qHeader else sql0)
                for row in cur0:
                    (t, device) = row[1:3]
                    if fp is None:
                        cur1 = db.cursor()
                        if qHeader:
                            fp = open(args.csv, "w")
                            fp.write(",".join(columns) + "\n")
                            qHeader = False
                        else:
                            fp = open(args.csv, "a")
                    fp.write(",".join(map(str, row)) + "\n")
                    cur1.execute(sqlq, (t, device))
                if fp is not None:
                    fp.close()

parser = argparse.ArgumentParser(description="Listen for a LiveGPS message")
MyLogger.addArgs(parser)
Writer.addArgs(parser)
Reader.addArgs(parser)
CSV.addArgs(parser)
args = parser.parse_args()

logger = MyLogger.mkLogger(args)
logger.info("args=%s", args)

try:
    writer = Writer(args, logger) # Create the db writer thread
    reader = Reader(writer.qIn, args, logger) # Create the UDP datagram reader thread
    csv = CSV(writer.qOut, args, logger) # Create the CSV file

    writer.start() # Start the writer thread
    reader.start() # Start the reader thread
    csv.start() # Start the CSV thread

    waitForException() # This will only raise an exception from a thread
except:
    logger.exception("Unexpected exception while listening")
