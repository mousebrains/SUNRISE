#! /usr/bin/python3
#
# Sync a set of folders to a another machine,
#
# May-2021, Pat Welch, pat@mousebrains.com

import inotify_simple as ins
import os
import logging
import argparse
import MyLogger
import queue
import time
import subprocess
from MyThread import MyThread

class Pusher(MyThread):
    def __init__(self, args:argparse.ArgumentParser,
            logger:logging.Logger, errQueue:queue.Queue) -> None:
        MyThread.__init__(self, "Pusher", logger, errQueue)
        self.__host = args.host
        self.__prefix = args.prefix
        self.__rsync = args.rsync
        self.__delay = args.delay
        self.__bwlimit = "--bwlimit=" + str(args.bwlimit)
        self.__retry = args.retry
        self.__extra = args.extra
        self.__queue = queue.Queue()
        
    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group(description="Pushing related options")
        grp.add_argument("--delay", type=int, default=10,
                help="Seconds after an inotify event until pushing started")
        grp.add_argument("--bwlimit", type=int, default=100, help="KB/sec to push data")
        grp.add_argument("--retry", type=int, default=60,
                help="Seconds between retries when pushing fails")
        grp.add_argument("--extra", type=float, default=1,
                help="Fudge seconds to reduce delay if multiple files are queued.")

        grp = parser.add_argument_group(description="Host related options")
        grp.add_argument("--host", type=str, default="glidervm3.ceoas.oregonstate.edu",
                help="Target machine to push/pull information from/to")
        grp.add_argument("--prefix", type=str, default="Dropbox",
                help="Path prefix on host machine")
        grp.add_argument("--rsync", type=str, default="/usr/bin/rsync",
                help="Rsync command to use")


    def put(self, path:str) -> None:
        self.__queue.put((time.time(), path))

    def runIt(self) -> None: # Called by MyThread on thread start
        logger = self.logger
        logger.info("Starting")
        q = self.__queue
        dt = None # Timeout
        delay = self.__delay
        files = {}
        tMin = None
        while True:
            now = time.time()
            dt = None if tMin is None else (delay - (now - tMin))
            if dt is not None and dt <= 0:
                (files, tMin) = self.syncIt(files, now)
                dt = None if tMin is None else (delay - (now - tMin))
            try:
                msg = q.get(timeout=dt)
                if len(msg) != 2:
                    logger.warning("Unexpected msg, %s", msg)
                    continue
                (t, path) = msg
                if tMin is None:
                    tMin = t
                logger.info("t %s %s path %s dt %s", t, tMin, path, dt)
                if path not in files:
                    files[path] = t
            except queue.Empty:
                pass

    def syncIt(self, files:dict, now:float) -> tuple[dict, float]:
        tThreshold = now - self.__delay + self.__extra 
        tMin = None
        nFiles = {}
        aFiles = set()
        for fn in files:
            t = files[fn]
            if t > tThreshold:
                tMin = t if tMin is None else min(tMin, t)
                nFiles[fn] = t
            else:
                aFiles.add(fn)

        if not self.runSync(aFiles):
            tPrime = now + self.__retry
            tMin = tPrime if tMin is None else min(tMin, tPrime)
            for fn in aFiles:
                nFiles[fn] = tPrime

        return (nFiles, tMin)

    def runSync(self, files:set) -> bool:
        cmd = [self.__rsync,
                self.__bwlimit,
                "--compress",
                "--compress-level=9",
                "--archive",
                "--mkpath",
                "--copy-unsafe-links",
                "--delete-missing-args",
                "--delete"
                ]
        cmd.extend(list(files))
        cmd.append(self.__host + ":" + self.__prefix)
        sp = subprocess.run(args=cmd, 
                shell=False,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
        if sp.returncode == 0:
            self.logger.info("Synced %s", ",".join(list(files)))
            return True
        try:
            output = str(sp.stdout, "utf-8")
        except:
            output = sp.stdout
        self.logger.warning("runSync %s\n%s\n%s", files, " ".join(cmd), output)
        return False

class Watcher(MyThread):
    def __init__(self, args:argparse.ArgumentParser, pusher:Pusher,
            logger:logging.Logger, errQueue:queue.Queue) -> None:
        MyThread.__init__(self, "Watcher", logger, errQueue)
        self.__pusher = pusher
        self.__init = not args.noinitial
        self.__inotify = ins.INotify()
        self.__wd = {}
        flags = ins.flags.CREATE \
                | ins.flags.MODIFY \
                | ins.flags.CLOSE_WRITE \
                | ins.flags.MOVED_TO \
                | ins.flags.MOVED_FROM \
                | ins.flags.MOVE_SELF \
                | ins.flags.DELETE \
                | ins.flags.DELETE_SELF
        for src in args.src:
            self.__wd[self.__inotify.add_watch(os.path.abspath(src), flags)] = src

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group(description="Pushing related options")
        grp.add_argument("--src", type=str, action="append", required=True,
                help="Folder(s) to push to the host")
        grp.add_argument("--noinitial", action="store_true", help="Don't do an initial sync")

    def runIt(self) -> None: # Called by MyThread on thread start
        logger = self.logger
        inotify = self.__inotify # Inotify handle
        wd = self.__wd # Watched directories
        for key in wd:
            logger.info("Watching %s", wd[key])
            if self.__init:
                self.__pusher.put(wd[key])

        while True:
            for event in inotify.read(): # Wait for an event, then read it
                flags = []
                for flag in ins.flags.from_mask(event.mask):
                    flags.append(str(flag)[6:])
                path = os.path.join(wd[event.wd], event.name)
                logger.info("path %s %s", path, ",".join(flags))
                self.__pusher.put(path)

parser = argparse.ArgumentParser(description="SUNRISE Cruise syncing")
MyLogger.addArgs(parser)
Pusher.addArgs(parser)
Watcher.addArgs(parser)

args = parser.parse_args()

logger = MyLogger.mkLogger(args)

logger.info("args %s", args)

errQueue = queue.Queue() # Errors from 
try:
    threads = []
    threads.append(Pusher(args, logger, errQueue))
    threads.append(Watcher(args, threads[0], logger, errQueue))
    for thrd in threads:
        thrd.start()

    raise(errQueue.get()) # Any errors are raised
except:
    logger.exception("Unexpected exception")
