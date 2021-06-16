#! /usr/bin/env python3
#
# Listen for the Walton Smith's AIS which is sent on port 8982
#
# Jun-2021, Pat Welch, pat@mousebrains.com

import ais.stream
import queue
import json
import datetime
import socket
import argparse
import threading
import time
import MyLogger
import logging
import argparse
import os
from MyThread import MyThread,waitForException

class Reader(MyThread):
    ''' Read datagrams from a socket and forward them to a socket so we catch all the datagrams '''
    def __init__(self, queue:queue.Queue,
            args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.__init__(self, "Reader", args, logger)
        self.__queue = queue
        self.__port = args.port
        self.__size = args.size

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group(description="UDP Listener options")
        grp.add_argument('--port', type=int, default=8982, metavar='port', help='Port to listen on')
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
    ''' Wait on a queue, decrypt them, then save the results in a growing CSV file '''
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.__init__(self, "Writer", args, logger)
        self.qIn = queue.Queue()

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        parser.add_argument("--csv", type=str, required=True, help="Output CSV filename")

    def __decrypt(self, msg:bytes) -> list:
        pass

    def __writeCSV(self, fields:list) -> None:
        if fields is None: return
        with open(self.args.csv, "a") as fp:
            fp.write(",".join(fields) + "\n")

    def runIt(self) -> None:
        '''Called on thread start '''
        qIn = self.qIn
        logger = self.logger
        logger.info("Starting")
        while True: # Loop forever
            (t, addr, msg) = qIn.get()
            (ipAddr, port) = addr
            logger.info("t %s addr %s %s\n%s", t, ipAddr, port, msg)
            # Decrypt the msg
            # fields = self.__decrypt(msg)
            # write CSV records
            # self.__writeCSV(fields)
            qIn.task_done()

parser = argparse.ArgumentParser(description="Listen for a LiveGPS message")
MyLogger.addArgs(parser)
Writer.addArgs(parser)
Reader.addArgs(parser)
args = parser.parse_args()

logger = MyLogger.mkLogger(args)
logger.info("args=%s", args)

try:
    writer = Writer(args, logger) # Create the db writer thread
    reader = Reader(writer.qIn, args, logger) # Create the UDP datagram reader thread

    writer.start() # Start the writer thread
    reader.start() # Start the reader thread

    waitForException() # This will only raise an exception from a thread
except:
    logger.exception("Unexpected exception while listening")
