#! /usr/bin/env python3
#
# Listen to a socket
# When a connection is made,
# spawn a thread, parse the message,
# and send to the writer thread.
#
# Feb-2020, Pat Welch, pat@mousebrains.com

import queue
import json
import datetime
import sqlite3
import socket
import argparse
import threading
import time
import MyLogger
import logging
import argparse
import os
import numpy as np
from MyThread import MyThread,waitForException

class Reader(MyThread):
    ''' Wait on a queue, and write the item to a file '''
    def __init__(self, queue:queue.Queue,
            args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.__init__(self, "Reader", args, logger)
        self.__queue = queue
        self.__port = args.port
        self.__size = args.size

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group(description="UDP Listener options")
        grp.add_argument('--port', type=int, required=True, metavar='port', help='Port to listen on')
        grp.add_argument("--size", type=int, default=65536, help="Datagram size")

    def runIt(self) -> None:
        '''Called on thread start '''
        q = self.__queue
        logger = self.logger
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            logger.debug("Opened UDP socket")
            s.bind(('', self.__port))
            logger.info('Bound to port %s', self.__port)
            while True: # Read datagrams
                (data, senderAddr) = s.recvfrom(self.__size)
                t = time.time()
                logger.info("Received from %s\n%s", senderAddr, data)
                q.put((t, senderAddr, data))

class Writer(MyThread):
    ''' Wait on a queue, and write the item to a file '''
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.__init__(self, "Writer", args, logger)
        self.qIn = queue.Queue()
        self.qOut = queue.Queue()

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group(description="Database writer options")
        grp.add_argument("--table", type=str, default="fixes", metavar='fixes',
                help="SQLite3 table name")
        grp.add_argument("--db", type=str, required=True, metavar='filename',
                help="SQLite3 database filename")

    def mkTable(self, cur:sqlite3.Cursor) -> None:
        tbl = self.args.table
        sql = "CREATE TABLE IF NOT EXISTS " + tbl + "(\n"
        sql+= " tRecv Real,\n"
        sql+= " ipAddr TEXT,\n"
        sql+= " port INTEGER,\n"
        sql+= " t TEXT,\n"
        sql+= " device TEXT,\n"
        sql+= " latitude REAL,\n"
        sql+= " longitude REAL,\n"
        sql+= " qCSV BOOL DEFAULT 0,\n"
        sql+= " PRIMARY KEY(t, device)\n"
        sql+= " );"
        cur.execute(sql)
        cur.execute("CREATE INDEX IF NOT EXISTS " + tbl + "_qCSV ON " + tbl + " (qCSV);")

    def runIt(self) -> None:
        '''Called on thread start '''
        qIn = self.qIn
        qOut = self.qOut
        logger = self.logger
        sql = "INSERT OR IGNORE INTO " + self.args.table + " VALUES(?,?,?,?,?,?,?,0);"
        logger.info("Starting SQL\n%s", sql)
        while True: # Loop forever
            (t, addr, msg) = qIn.get()
            (ipAddr, port) = addr
            with sqlite3.connect(self.args.db) as db:
                cur = db.cursor()
                cur.execute("BEGIN;")
                self.mkTable(cur)
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
        columns = ("tRecv", "t", "device", "latitude", "longitude")
        sql0 = "SELECT " + ",".join(columns) + " FROM " + args.table + " WHERE qCSV=0 ORDER BY t;"
        sql1 = "SELECT " + ",".join(columns) + " FROM " + args.table + " ORDER BY t;"
        sqlq = "UPDATE " + args.table + " SET qCSV=1  WHERE t=? AND device=?;"

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

class Faux(MyThread):
    ''' Generate Fake datagrams '''

    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.__init__(self, "Faux", args, logger)
        self.__lat = args.faux_lat
        self.__lon = args.faux_lon
        self.__tPrev = None
        if args.seed is not None:
            np.seed(args.seed)

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group()
        grp.add_argument("--faux_dt", type=float, help="Time between faux datagrams")
        grp.add_argument("--faux_lat", type=float, default=29, help="Initial faux latitude")
        grp.add_argument("--faux_lon", type=float, default=-93.5, help="Initial faux longitude")
        grp.add_argument("--faux_vel_lat", type=float, default=1e-6,
                help="average latitude velocity deg/sec")
        grp.add_argument("--faux_vel_lon", type=float,  default=1e-6,
                help="average longitude velocity deg/sec")
        grp.add_argument("--faux_var_lat", type=float, default=1e-7,
                help="average latitude variance deg/sec")
        grp.add_argument("--faux_var_lon", type=float, default=1e-7,
                help="average longitude variance deg/sec")
        grp.add_argument("--seed", type=int, help="Numpy random seed")

    def __mkDatagram(self) -> None:
        tPrev = self.__tPrev
        now = datetime.datetime.now()
        if tPrev is not None:
            dt = (now - tPrev).total_seconds()
            self.__lat += np.random.normal(loc=args.faux_vel_lat, scale=args.faux_var_lat) * dt
            self.__lon += np.random.normal(loc=args.faux_vel_lon, scale=args.faux_var_lon) * dt
        self.__tPrev = now
        lat = self.__lat
        lon = self.__lon
        msg = json.dumps([{
                "device_name": None,
                "serial_number": "FAUX",
                "lat": "{:.6f}".format(lat),
                "lng": "{:.6f}".format(lon),
                "location_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                }])


        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            self.logger.info("Sending datagram\n%s", msg)
            s.sendto(bytes(msg, "UTF-8"), ("127.0.0.1", self.args.port))



    def runIt(self) -> None: # Called on thread start
        args = self.args
        logger = self.logger
        delta = args.faux_dt
        if delta is None:
            logger.info("Not starting")
            return
        logger.info("Starting")
        now = time.time()
        tNext = now + delta
        while True:
            dt = tNext - now
            tNext += delta
            if dt >= 0.1: # wait a bit
                logger.info("Sleeping for %s seconds", dt)
                time.sleep(dt)
            self.__mkDatagram()
            now = time.time()
            while tNext <= now: tNext += delta

parser = argparse.ArgumentParser(description="Listen for a LiveGPS message")
MyLogger.addArgs(parser)
Writer.addArgs(parser)
Reader.addArgs(parser)
CSV.addArgs(parser)
Faux.addArgs(parser)
args = parser.parse_args()

logger = MyLogger.mkLogger(args)
logger.info("args=%s", args)

try:
    writer = Writer(args, logger) # Create the db writer thread
    reader = Reader(writer.qIn, args, logger) # Create the UDP datagram reader thread
    csv = CSV(writer.qOut, args, logger) # Create the CSV file
    faux = Faux(args, logger) # Generate Faux data

    writer.start() # Start the writer thread
    reader.start() # Start the reader thread
    csv.start() # Start the CSV thread
    faux.start() # Start up the faux data

    waitForException() # This will only raise an exception from a thread
except:
    logger.exception("Unexpected exception while listening")
