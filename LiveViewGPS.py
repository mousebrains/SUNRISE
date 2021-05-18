#! /usr/bin/env python3
#
# Listen to a socket
# When a connection is made,
# spawn a thread, parse the message,
# and send to the writer thread.
#
# Feb-2020, Pat Welch, pat@mousebrains.com

import socket
import argparse
import threading
import time
import MyLogger
from Writer import Writer
from Reader import Reader
from MyThread import waitForException

parser = argparse.ArgumentParser(description="Listen for a LiveGPS message")
MyLogger.addArgs(parser)
Writer.addArgs(parser)
Reader.addArgs(parser)
args = parser.parse_args()

logger = MyLogger.mkLogger(args)
logger.info("args=%s", args)

try:
    writer = Writer(args, logger) # Create the db writer thread
    queues = [writer.q]
    reader = Reader(args, queues, logger) # Create the UDP datagram reader thread

    logger.info("Starting writer")
    writer.start() # Start the writer thread
    logger.info("Starting reader")
    reader.start() # Start the reader thread

    logger.info("Waiting")
    waitForException() # This will only raise an exception from a thread
except:
    logger.exception("Unexpected exception while listening")
