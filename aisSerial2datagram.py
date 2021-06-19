#! /usr/bin/python3
#
# Translate serial messages into datagrams for the R/V Pelican's AIS feed
#
import serial
import argparse
import MyLogger
import logging
import socket
import MyThread
import queue
import yaml

class Reader(MyThread.MyThread):
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger, 
            q:queue.Queue) -> None:
        MyThread.MyThread.__init__(self, "RDR", args, logger)
        self.queue = q

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group(description="Serial port options")
        grp.add_argument("--port", type=str, default="/dev/ttyUSB0", help="Serial port")
        grp.add_argument("--baudrate", type=int, 
                choices=(1200,2400,4800,9600,19200,38400,115200),
                default=38400, help="Serial port baud rate")
        
        # grp.add_argument("--bits", type=int, choices=(7,8), help="Number of bits")
        # grp.add_argument("--stopbits", type=float, choices=(1,1.5,2), help="Number of stop bits")
        # grp.add_argument("--parity", type=str, choices=("even", "odd", "none"), help="Parity")

    def runIt(self) -> None: # Called on thread start
        args = self.args
        logger = self.logger
        with serial.Serial(args.port, args.baudrate) as s:
            while True:
                line = s.readline().strip()
                logger.info("line %s", line)
                self.queue.put(line)

class AIS(MyThread.MyThread):
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.MyThread.__init__(self, "AIS", args, logger)
        self.queue = queue.Queue()
        self.targets = []
        for fn in args.config: self.loadConfig(fn)

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group(description="Datagram AIS")
        grp.add_argument("--config", type=str, action="append", required=True,
                help="config file(s) containing ipv4:port to send datagrams to, 192.168.0.11:8982")

    def loadConfig(self, fn:str) -> None:
        self.logger.info("Loading %s", fn)
        with open(fn, "r") as fp:
            data = yaml.safe_load(fp)
            for item in data:
                if "ip" not in item or "port" not in item:
                    logger.error("Unrecognized entry, %s in %s", item, fn)
                    continue
                try:
                    item["port"] = int(item["port"])
                    self.targets.append(item)
                except:
                    logger.error("Converting %s to an int in %s", item["port"], item)

    def runIt(self) -> None: # Called on thread start
        args = self.args
        logger = self.logger
        q = self.queue
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        while True:
            msg = q.get()
            q.task_done()
            for item in self.targets:
                s.sendto(msg, (item["ip"], item["port"]))

parser = argparse.ArgumentParser()
MyLogger.addArgs(parser)
AIS.addArgs(parser)
Reader.addArgs(parser)
args = parser.parse_args()

logger = MyLogger.mkLogger(args)

try:
    ais = AIS(args, logger)
    rdr = Reader(args, logger, ais.queue)
    ais.start()
    rdr.start()

    MyThread.waitForException()
except:
    logger.exception("Unexpected exception")
