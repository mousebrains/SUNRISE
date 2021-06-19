#! /usr/bin/env python3
#
# Set up an inotify watcher on some directories,
# then trigger to generate plots
#
# June-2021, Pat Welch, pat@mousebrains.com

import MyLogger
import MyInotify
import MyThread
import logging
import argparse
import os.path
import queue
import time

class Trigger(MyThread.MyThread):
    def __init__(self, queue:queue.Queue,
            args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.MyThread.__init__(self, "Trigger", args, logger)
        self.__queue = queue

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        pass

    def runIt(self) -> None: # Called on thread start
        q = self.__queue
        logger = self.logger
        logger.info("Starting")
        while True:
            (action, t, names) = q.get()
            q.task_done()
            logger.info("action %s t %s names %s", action, t, names)
            # Lixin insert trigger code here for subprocess

parser = argparse.ArgumentParser()
MyLogger.addArgs(parser)
Trigger.addArgs(parser)
parser.add_argument("dir", nargs="+", type=str, help="Directory trees to monitor")
args = parser.parse_args()

logger = MyLogger.mkLogger(args)
logger.info("args=%s", args)

try:
    inotify = MyInotify.MyInotify(args, logger)
    trigger = Trigger(inotify.queue, args, logger)
    
    for item in args.dir:
        inotify.addTree(item)

    inotify.start()
    trigger.start()
    
    MyThread.waitForException()
except:
    logger.exception("Unexpected exception")
