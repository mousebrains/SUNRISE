#! /usr/bin/env python3
#
# Listen for to a UDP port for datagrams and record them in an SQLite3 database
#
# Jun-2021, Pat Welch, pat@mousebrains.com

import queue
import socket
import argparse
import time
import MyLogger
import logging
import MyThread
import os
import sqlite3

class Reader(MyThread.MyThread):
    ''' Read datagrams from a socket and forward them to a socket so we catch all the datagrams '''
    def __init__(self, q:queue.Queue, args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.MyThread.__init__(self, "RDR", args, logger)
        self.__queue = q

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group(description="UDP Listener options")
        grp.add_argument('--port', type=int, default=8982, metavar='port', help='Port to listen on')
        grp.add_argument("--size", type=int, default=65536, help="Datagram size")

    def runIt(self) -> None:
        '''Called on thread start '''
        q = self.__queue
        logger = self.logger
        args = self.args
        logger.info("Starting %s %s", args.port, args.size)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            logger.debug("Opened UDP socket")
            s.bind(('', args.port))
            logger.info('Bound to port %s', args.port)
            while True: # Read datagrams
                (data, senderAddr) = s.recvfrom(args.size)
                t = time.time()
                (ipAddr, port) = senderAddr
                logger.info("Received from %s %s\n%s", ipAddr, port, data)
                q.put((t, ipAddr, port, data))

class Writer(MyThread.MyThread):
    ''' Wait on a queue, decrypt them, then save the results in a growing JSON file '''
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.MyThread.__init__(self, "Writer", args, logger)
        self.qIn = queue.Queue()
        
    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        parser.add_argument("--db", type=str, required=True,
                help="Output SQLite3 database filename")
        
    def runIt(self) -> None:
        '''Called on thread start '''
        qIn = self.qIn
        logger = self.logger
        args = self.args
        logger.info("Starting %s", args.db)

        dbDir = os.path.dirname(args.db)
        if dbDir and not os.path.isdir(dbDir):
            logger.info("Making %s", dbDir)
            os.makedirs(dbDir, mode=0o7775)

        sql = "CREATE TABLE IF NOT EXISTS raw (\n"
        sql+= "  t REAL,\n"
        sql+= "  addr TEXT,\n"
        sql+= "  port INTEGER,\n"
        sql+= "  msg TEXT\n"
        sql+= ");\n"

        with sqlite3.connect(args.db) as db:
            cur = db.cursor()
            cur.execute("BEGIN;")
            cur.execute(sql)
            cur.execute("COMMIT;")

        while True: # Loop forever
            (t, ipAddr, port, msg) = qIn.get()
            logger.info("t %s addr %s %s\n%s", t, ipAddr, port, msg)
            with sqlite3.connect(args.db) as db:
                cur = db.cursor()
                cur.execute("BEGIN;")
                cur.execute("INSERT INTO raw VALUES(?,?,?,?);", (t, ipAddr, port, msg))
                cur.execute("COMMIT;")
            qIn.task_done()

parser = argparse.ArgumentParser(description="Listen for a AIS datagrams")
MyLogger.addArgs(parser)
Writer.addArgs(parser)
Reader.addArgs(parser)
parser.add_argument("--timeout", type=float, help="Timeout after this many seconds")
args = parser.parse_args()

logger = MyLogger.mkLogger(args)
logger.info("args=%s", args)

try:
    writer = Writer(args, logger) # Create the db writer thread
    reader = Reader(writer.qIn, args, logger) # Create the UDP datagram reader thread

    writer.start() # Start the writer thread
    reader.start() # Start the reader thread
    MyThread.waitForException(args.timeout) # This will only raise an exception from a thread
except:
    logger.exception("Unexpected exception while listening to port %s", args.port)
