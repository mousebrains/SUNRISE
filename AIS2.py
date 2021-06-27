#! /usr/bin/env python3
#
# 1) Listen for AIS packets on a UDP port
# 2) Save the raw packets in a database for replaying in the future
# 3) Decrypt packets.
# 4) Save the decrypted JSON packets in a database
# 5) Save a spare version of the MMSI, timestamp, latitude, and longitude in a CSV file
#
# This was built for the SUNRISE 2021 research cruise
#
# Jun-2021, Pat Welch, pat@mousebrains.com
# Jun-2021, Ross Synder

import queue
import json
import datetime
import socket
import time
import MyThread
import MyLogger
import logging
import argparse
import os
import sqlite3
import re
import ais # This adds a stream handler to logging for some dumb/stupid reason!

class Reader(MyThread.MyThread):
    ''' Read datagrams from a socket and forward them to a various queues. '''
    def __init__(self, queues:list[queue.Queue],
            args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.MyThread.__init__(self, "Reader", args, logger)
        self.__queues = queues

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group(description="UDP Listener options")
        grp.add_argument("--port", type=int, default=8982, metavar='port', 
                help='UDP port to listen on')
        # NEMA sentences have a maximum size of 82 bytes, but there can
        # be multiple NEMA sentences in a datagram for multipart payloads.
        # so take a guess at 20 * NEMA+3
        grp.add_argument("--size", type=int, default=20*85, help="Datagram size")

    def put(self, t, ipAddr, port, data) -> None:
        ''' send this information to the queues I know about, for replaying and real '''
        msg = (t, ipAddr, port, data)
        for q in self.__queues: q.put(msg)

    def runIt(self) -> None:
        '''Called on thread start '''
        logger = self.logger
        args = self.args
        logger.info("Starting %s %s", args.port, args.size)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            logger.debug("Opened UDP socket")
            s.bind(('', args.port))
            logger.info('Bound to port %s', args.port)
            while True: # Read datagrams
                (data, senderAddr) = s.recvfrom(args.size)
                t = time.time() # Timestamp just after the packet was received
                (ipAddr, port) = senderAddr
                logger.info("Received from %s %s\n%s", ipAddr, port, data)
                self.put(t, ipAddr, port, data)

class Replay(MyThread.MyThread):
    ''' Reader messages from a database and feed them into the system via Reader.put '''
    def __init__(self, rdr:Reader, args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.MyThread.__init__(self, "Replay", args, logger)
        self.__reader = rdr

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        parser.add_argument("--replay", type=str, metavar='foo.db', 
                help="Database to read raw records from")

    def runIt(self) -> None: # Called on thread start
        logger = self.logger
        args = self.args
        rdr = self.__reader
        if args.replay is None:
            logger.info("No need to run, --replay not specified")
            return
        logger.info("Starting %s", args.replay)
        cnt = 0
        with sqlite3.connect(args.replay) as db:
            cur = db.cursor()
            cur.execute("SELECT t,addr,port,msg FROM raw ORDER by t;")
            for row in cur:
                (t, addr, port, msg) = row
                rdr.put(t, addr, port, msg)
                cnt += 1
        logger.info("Sent %s messages to the Reader's queue", cnt)

class Raw2DB(MyThread.MyThread):
    ''' Wait on a queue, record the messages in an SQLite3 database for future replay '''
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.MyThread.__init__(self, "Raw2DB", args, logger)
        self.qIn = queue.Queue()

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        parser.add_argument("--raw", type=str, help="Database with raw table")

    @staticmethod
    def qUse(args:argparse.ArgumentParser) -> bool:
        return args.raw is not None

    def __mkTable(self) -> None:
        ''' Create a raw table if it does not exist '''
        sql = "CREATE TABLE IF NOT EXISTS raw (\n"
        sql+= "  t REAL,\n"
        sql+= "  addr TEXT,\n"
        sql+= "  port INTEGER,\n"
        sql+= "  msg TEXT,\n"
        sql+= "  PRIMARY KEY(t, msg)\n"
        sql+= ");\n"
        with sqlite3.connect(self.args.raw) as db:
            cur = db.cursor()
            cur.execute("BEGIN;")
            cur.execute(sql)
            cur.execute("COMMIT;")

    def runIt(self) -> None: # Called on thread start
        logger = self.logger
        args = self.args
        q = self.qIn
        logger.info("Starting %s", args.raw)
        self.__mkTable()
        while True:
            msg = q.get()
            with sqlite3.connect(args.raw) as db:
                cur = db.cursor()
                cur.execute("BEGIN;")
                cur.execute("INSERT OR IGNORE INTO raw VALUES(?,?,?,?);", msg)
                cur.execute("COMMIT;")
            q.task_done()

class Decrypter(MyThread.MyThread):
    ''' Wait on a queue, decrypt the AIS messages, then pass them onto other queues '''
    def __init__(self, queues:list[queue.Queue],
            args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.MyThread.__init__(self, "Decrypt", args, logger)
        self.qIn = queue.Queue()
        self.__queues = queues # Output queues
        self.__partials = {} # For accumulating multipart messages

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        pass # I don't have any options

    def __denema(self, msg:bytes) -> list:
        # Check the NEMA sentence structure is good, then take the message apart into fields
        # field[0] -> !AIVD[MO]
        # field[1] -> Total number of fragments, for single part messages, this is 1
        # field[2] -> Fragment number, for single part messages this is 1
        # field[3] -> multipart identification count
        # field[4] -> Radio channel, A or 1 -> 161.975MHz B or 2 -> 162.025MHz
        # field[5] -> data payload
        # field[6] -> number of fill bits
        matches = re.match(b"\s*!(AIVD[MO],\d+,\d+,\d?,\w?,.*,[0-5])[*]([0-9A-Za-z]{2})\s*", msg)
        if not matches: return None

        chksum = 0
        for c in matches[1]: chksum ^= c

        sentChkSum = int(str(matches[2], "UTF-8"), 16)
        if chksum != sentChkSum:
            print("Bad checksum,", chksum, sentChkSum)
            return None

        fields = str(matches[1], "UTF-8").split(",")
        if len(fields) != 7: return None
        fields[1] = int(fields[1]) # Number of fragments
        fields[2] = int(fields[2]) # Fragment number
        fields[6] = int(fields[6]) # Fill bits
        return fields

    def __agePartials(self, t:float) -> None: # Maximum age to avoid memory leaks
        info = self.__partials # Partial message information

        for ident in info:
            tAge = info[ident]["age"]
            # Give 1 minute for partial messages to accumulate
            if tAge > (t - 60): continue 
            logger.warning("Aged out %s", ident)
            del info[ident]

    def __accumulate(self, t, fields:list) -> bool:
        if fields[1] == 1: return fields # No need to Accumulate

        info = self.__partials # previous information on partial messages
        ident = fields[3] # Partial message identifier

        if ident not in info:  # First time this ident has been seen
            info[ident] = {"payloads": {}, "fillBits": 0, "age": t}

        info[ident]["payloads"][fields[2]] = fields[5] # Accumulate payloads

        if fields[1] == fields[2]: # Number of fill bits on last segment
            info[ident]["fillBits"] = fields[6]

        if len(info[ident]["payloads"]) != fields[1]: # Need to accumulate some more
            self.__agePartials(t) # Avoid memory leaks
            return None

        # Build 
        payload = ""
        for key in sorted(info[ident]["payloads"]): # Make parts are assembled in correct order
            payload += info[ident]["payloads"][key]

        fields[5] = payload
        fields[6] = info[ident]["fillBits"]
        del info[ident]
        return fields

    def runIt(self) -> None: # Called on thread start
        qIn = self.qIn
        queues = self.__queues
        self.logger.info("Starting")

        while True:
            (t, addr, port, data) = qIn.get()
            qIn.task_done()
            logger.debug("Received %s %s %s %s", t, addr, port, data)
            # there might be multiple messages in a single datagram
            for sentence in data.strip().split(b"\n"):
                fields = self.__denema(sentence)
                if fields is None: # Not a valid sentence, so skip it
                    logger.info("Bad NEMA %s %s %s %s", t, addr, port, sentence)
                    continue
                if fields[1] != 1: # Need to accumulate
                    fields = self.__accumulate(t, fields)
                    if fields is None: continue # Partial payload, so wait for more

                info = ais.decode(fields[5], fields[6])
                if info is None: continue
                # Don't deal with timestamp, utc_min, and utc_hour, just use the time received
                t0 = datetime.datetime.fromtimestamp(round(t), tz=datetime.timezone.utc)
                info["t"] = t0.strftime("%Y-%m-%d %H:%M:%S")
                logger.debug("Info %s", info)
                for q in queues: q.put((t, info))

class DB(MyThread.MyThread):
    ''' Wait on a queue and save the resulting JSON to an SQLite3 database '''
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.MyThread.__init__(self, "DB", args, logger)
        self.qIn = queue.Queue()

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        parser.add_argument("--db", type=str, help="JSON DB filename")

    @staticmethod
    def qUse(args:argparse.ArgumentParser) -> bool:
        return args.db is not None

    def __mkTable(self) -> None:
        ''' Create a JSON table if it does not exist '''
        sql = "CREATE TABLE IF NOT EXISTS json (\n"
        sql+= "  t REAL,\n"
        sql+= "  mmsi TEXT,\n"
        sql+= "  json TEXT,\n"
        sql+= "  PRIMARY KEY(t, json)\n"
        sql+= ");\n"
        with sqlite3.connect(self.args.db) as db:
            cur = db.cursor()
            cur.execute("BEGIN;")
            cur.execute(sql)
            cur.execute("CREATE INDEX IF NOT EXISTS json_mmsi ON json (mmsi);")
            cur.execute("COMMIT;")

    def runIt(self) -> None: # Called on thread start
        logger = self.logger
        args = self.args
        q = self.qIn
        logger.info("Starting %s", args.db)
        self.__mkTable()
        while True:
            (t,msg) = q.get()
            txt = json.dumps(msg, separators=(",",":"))
            with sqlite3.connect(args.db) as db:
                cur = db.cursor()
                cur.execute("BEGIN;")
                cur.execute("INSERT OR IGNORE INTO json VALUES(?,?,?);", 
                        (t, msg["mmsi"] if "mmsi" in msg else None, txt))
                cur.execute("COMMIT;")
            q.task_done()

class BaseOutput(MyThread.MyThread):
    ''' Base class for CSV and JSON '''
    def __init__(self, name:str, dt:float, 
            args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.MyThread.__init__(self, name, args, logger)
        self.qIn = queue.Queue()
        self.dt = dt
        self.qSeen = {}
        self.requiredFields = set(["mmsi", "x", "y"])
        self.fields = (("t", None), ("mmsi", None), ("x", 6), ("y", 6))
        self.optional = (("cog", 0), ("sog", 1))

    def roundIt(self, val, rnd:int):
        if rnd is None: return val
        if rnd == 0: return int(val)
        return round(val, rnd)

    def makeDirs(self, fn:str) -> None:
        dirName = os.path.dirname(fn)
        if dirName and not os.path.isdir(dirName):
            logger.info("Making %s", dirName)
            os.makedirs(dirName, mode=0o775)

    def qOutput(self, t:float, msg:tuple) -> bool:
        for key in self.requiredFields:
            if key not in msg: return False
        mmsi = msg["mmsi"]
        if (mmsi in self.qSeen) and ((self.qSeen[mmsi] + self.dt) > t): return False
        self.qSeen[mmsi] = t
        return True

class CSV(BaseOutput):
    ''' Wait on a queue, send a sparse version of the records to a CSV file '''
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        BaseOutput.__init__(self, "CSV", args.dtCSV, args, logger)
        
    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group(description="CSV related options")
        grp.add_argument("--csv", type=str, help="Output CSV filename")
        grp.add_argument("--dtCSV", type=float, default=60,
                help="Seconds between messages for the same MMSI")

    @staticmethod
    def qUse(args:argparse.ArgumentParser) -> bool:
        return args.csv is not None

    def __writeHeader(self) -> None:
        if os.path.exists(args.csv): return
        hdr = []
        for row in self.fields: hdr.append(row[0])
        with open(args.csv, "w") as fp:
            fp.write(",".join(hdr) + "\n")

    def __writeRow(self, row:dict) -> None:
        record = []
        for (key, rnd) in self.fields:
            if key not in row: 
                record.append("")
            else:
                record.append(str(self.roundIt(row[key], rnd)))

        record = ",".join(record)
        logger.info("%s", record)

        with open(self.args.csv, "a") as fp:
            fp.write(record)
            fp.write("\n")

    def runIt(self) -> None: # Called on thread start
        qIn = self.qIn
        logger = self.logger
        args = self.args
        logger.info("Starting %s %s", args.csv, args.dtCSV)
        self.makeDirs(args.csv)
        self.__writeHeader()

        while True: # Loop forever
            (t, msg) = qIn.get()
            if self.qOutput(t, msg):
                self.__writeRow(msg)
            qIn.task_done()

class JSON(BaseOutput):
    ''' Wait on a queue, send a sparse version of the records to a JSON file '''
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        BaseOutput.__init__(self, "JSON", args.dtJSON, args, logger)
        
    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group(description="JSON related options")
        grp.add_argument("--json", type=str, help="Output json filename")
        grp.add_argument("--dtJSON", type=float, default=60,
                help="Seconds between messages for the same MMSI")

    @staticmethod
    def qUse(args:argparse.ArgumentParser) -> bool:
        return args.json is not None

    def __writeRow(self, row:dict) -> None:
        toKeep = {}
        for (key, rnd) in self.fields:
            if key not in row: continue
            toKeep[key] = self.roundIt(row[key], rnd)
        for (key, rnd) in self.optional:
            if key not in row: continue
            toKeep[key] = self.roundIt(row[key], rnd)

        if not toKeep: return

        with open(self.args.json, "a") as fp:
            msg = json.dumps(toKeep, separators=(",",":"), sort_keys=True) # Compact form
            logger.info("%s", msg)
            fp.write(msg)
            fp.write("\n")

    def runIt(self) -> None: # Called on thread start
        qIn = self.qIn
        logger = self.logger
        args = self.args
        logger.info("Starting %s %s", args.json, args.dtJSON)
        self.makeDirs(args.json)

        while True: # Loop forever
            (t, msg) = qIn.get()
            if self.qOutput(t, msg):
                self.__writeRow(msg)
            qIn.task_done()

parser = argparse.ArgumentParser(description="Listen for a AIS datagrams")
MyLogger.addArgs(parser)
Reader.addArgs(parser)
Replay.addArgs(parser)
Raw2DB.addArgs(parser)
Decrypter.addArgs(parser)
DB.addArgs(parser)
CSV.addArgs(parser)
JSON.addArgs(parser)
parser.add_argument("--dt", type=float, help="Stop collecting data after this many seconds")
args = parser.parse_args()

logger = MyLogger.mkLogger(args)
logger.info("args=%s", args)

try:
    threads = []

    # Initially the threads that are feed by the decrypter
    queues = []
    if JSON.qUse(args):
        threads.append(JSON(args, logger))
        queues.append(threads[-1].qIn)
    if CSV.qUse(args):
        threads.append(CSV(args, logger))
        queues.append(threads[-1].qIn)
    if DB.qUse(args):
        threads.append(DB(args, logger))
        queues.append(threads[-1].qIn)

    threads.append(Decrypter(queues, args, logger))

    # Now things that are feed by Reader or Replay, which will always inclue the Decrypter
    queues = [threads[-1].qIn]

    if Raw2DB.qUse(args):
        threads.append(Raw2DB(args, logger))
        queues.append(threads[-1].qIn)
       
    # The Reader which feeds the Decrypter and possibly Raw2DB 
    threads.append(Reader(queues, args, logger))
    threads.append(Replay(threads[-1], args, logger)) # Replay may exit immediately

    for thrd in threads: thrd.start() # Start all the threads

    MyThread.waitForException(timeout=args.dt) # This will only raise an exception from a thread
except:
    logger.exception("Unexpected exception while listening")
