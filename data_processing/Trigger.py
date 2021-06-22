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
import subprocess
import re

class Trigger(MyThread.MyThread):
    def __init__(self, queue:queue.Queue,
            args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.MyThread.__init__(self, "Trigger", args, logger)
        self.__queue = queue
        self.__regexp = re.compile(r"/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}_.*yml")

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        pass

    def runIt(self) -> None: # Called on thread start
        q = self.__queue
        logger = self.logger
        logger.info("Starting")
        regexp = self.__regexp

        while True:
            (action, t, names) = q.get()
            q.task_done()
            # Go through the names and keep just the expected patterns, 
            # i.e. not the files rsync is still working on
            toKeep = set()
            for name in names:
                if regexp.search(name):
                    toKeep.add(name)

            if len(toKeep) == 0: continue # Nothing to do

            logger.info("action %s t %s names %s", action, t, toKeep)
            # Lixin insert trigger code here for subprocess
            cmd = ["/usr/bin/python3", "/home/pat/SUNRISE/data_processing/realtime.py"]
            cmd.extend(toKeep)
            process = subprocess.run(cmd, shell=False, check=False,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    universal_newlines=True)
            output = process.stdout
            try:
                output = str(output, "utf-8")
            except:
                pass

            if process.returncode: # Probably an error
                logger.error("Executing return code %s Command: %s\nOutput:\n%s",
                        process.returncode, " ".join(cmd), output)
            elif len(output): # Probably okay, but there was output
                logger.info("Command: %s\nOutput:\n%s", " ".join(cmd), output)

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
