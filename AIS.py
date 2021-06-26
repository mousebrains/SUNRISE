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
import csv
import math
from datetime import date
#import pandas as pd
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
    ''' Wait on a queue, decrypt them, then save the results in a growing JSON file '''
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.__init__(self, "Writer", args, logger)
        self.qIn = queue.Queue()
        
    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        parser.add_argument("--json", type=str, required=True, help="Output json filename")
        
    def __decrypt(self, msg:bytes) -> list:
        plaintext = msg.decode("utf-8")
        gramlist = plaintext.split("!");
        return ais.stream.decode(gramlist)
            

    def __writeJSON(self, fields:list) -> None:
        if fields is None: 
            logger.info("\n Write failed \n")
            return
        with open(self.args.json, "a") as fp:
            for d in fields:
                logger.info("Datagram: %s\n Writing to %s\n", d, self.args.json)
                json.dump(d, fp, separators=(",", ":"))
                fp.write("\n")
            

    def runIt(self) -> None:
        '''Called on thread start '''
        qIn = self.qIn
        logger = self.logger
        logger.info("Starting %s", self.args.json)

        jsonDir = os.path.dirname(self.args.json)
        if jsonDir and not os.path.isdir(jsonDir):
            logger.info("Making %s", jsonDir)
            os.makedirs(jsonDir, mode=0o7775)

        while True: # Loop forever
            (t, addr, msg) = qIn.get()
            (ipAddr, port) = addr
            logger.info("t %s addr %s %s\n%s", t, ipAddr, port, msg)
            # Decrypt the msg
            fields = self.__decrypt(msg)
            rf = []
            #dont save the fields we don't need
            for f in fields:
                if ("mmsi" not in f) or \
                        ("x" not in f) or \
                        ("y" not in f) or \
                        ("timestamp" not in f): 
                    logger.info("Skipping %s", f)
                    continue # Skip this entry, nothing to do
                toKeep = {
                        "mmsi": f["mmsi"],
                        "x": round(f["x"], 6),
                        "y": round(f["y"], 6),
                        }
                if "sog" in f: toKeep["sog"] = round(f["sog"], 1)
                if "cog" in f: toKeep["cog"] = int(f["sog"])
                now = datetime.datetime.now(tz=timezone.utc).replace(microsecond=0)
                t0 = now.replace(second=int(f["timestamp"]) % 60)
                if "utc_min" in f: t0.replace(minute=int(f["utc_min"]))
                if "utc_hour" in f: t0.replace(hour=int(f["utc_hour"]))
                if t0 > now: t0 -= datetime.timedelta(days=1)
                toKeep["t"] = int(t0.timestamp())
                rf.append(toKeep)
            #RF now contains only necessary fields
            #set the name for known mmsi id's
            #if str(rf[0]['mmsi']) in known:
            #    rf[0]['name'] = known[str(rf[0]['mmsi'])]
            if rf: self.__writeJSON(rf)
            qIn.task_done()

parser = argparse.ArgumentParser(description="Listen for a AIS datagrams")
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
