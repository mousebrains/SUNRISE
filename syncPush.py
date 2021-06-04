#! /usr/bin/python3
#
# Sync a set of folders to a another machine,
#
# May-2021, Pat Welch, pat@mousebrains.com

import MyInotify
import os
import logging
import argparse
import MyLogger
import queue
import time
import subprocess
import MyThread

class Pusher(MyThread.MyThread):
    def __init__(self, queue:queue.Queue,
            args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.MyThread.__init__(self, "Pusher", args, logger)
        self.__queue = queue
        self.__preCmd = [
                args.rsync,
                "--compress",
                "--compress-level=22",
                "--archive",
                "--mkpath",
                "--copy-unsafe-links",
                "--delete-missing-args",
                "--delete",
                "--relative",
                ]
        if args.stats: self.__preCmd.extend(["--stats"])
        if (args.bwlimit is not None) and (args.bwlimit > 0):
            self.__preCmd.extend(["--bwlimit", str(args.bwlimit)])
        
    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group(description="Pushing related options")
        grp.add_argument("--delay", type=int, default=10,
                help="Seconds after an inotify event until pushing started")
        grp.add_argument("--stats", action='store_true', help="Collect rsync stats")
        grp.add_argument("--bwlimit", type=int, help="KB/sec to push data")
        grp.add_argument("--retry", type=int, default=60,
                help="Seconds between retries when pushing fails")
        grp.add_argument("--extra", type=float, default=1,
                help="Fudge seconds to reduce delay if multiple files are queued.")

        grp = parser.add_argument_group(description="Host related options")
        grp.add_argument("--host", type=str, default="vm3",
                help="Target machine to push/pull information from/to")
        grp.add_argument("--prefix", type=str, default=".",
                help="Path prefix on host machine")
        grp.add_argument("--rsync", type=str, default="/usr/bin/rsync",
                help="Rsync command to use")
        grp.add_argument("--dryrun", action="store_true", help="Don't actually execute rsync")


    def runIt(self) -> None: # Called by MyThread on thread start
        args = self.args
        logger = self.logger
        logger.info("Starting")
        q = self.__queue
        dt = None # Timeout
        delay = args.delay # Delay after a notification before starting a sync
        tMin = None
        toSync = set() # Filenames to sync
        while True:
            now = time.time()
            dt = None if tMin is None else (delay - (now - tMin))
            # if dt is not None and dt <= 0:
                # (files, tMin) = self.syncIt(files, now)
                # dt = None if tMin is None else (delay - (now - tMin))
            try:
                logger.info("dt %s", dt)
                (action, t, files) = q.get(timeout=dt)
                logger.info("action %s t %s files %s", action, t, files)
                if tMin is None:
                    tMin = t
                logger.info("t %s %s dt %s", t, tMin, dt)
                toSync.update(files) # Add in new files to sync
                logger.info("toSync %s", toSync)
            except queue.Empty:
                (tMin, toSync) = self.syncIt(toSync)

    def syncIt(self, files:set) -> tuple[float, set]:
        if self.runSync(files):
            return (None, set()) # Succeded, so nothing more to do
        else: # Failed
            args = self.args
            return (time.time() + args.retry, files) # Failed, so try again after retry

    def runSync(self, files:set) -> bool:
        args = self.args
        cmd = self.__preCmd.copy()
        cmd.extend(files)
        cmd.append(args.host + ":" + args.prefix)
        self.logger.info("CMD:\n%s", " ".join(cmd))
        if args.dryrun:
            self.logger.info("CMD: %s", cmd)
            return True
        sp = subprocess.run(args=cmd, 
                shell=False,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
        try:
            output = str(sp.stdout, "utf-8")
        except:
            output = sp.stdout

        if sp.returncode == 0:
            self.logger.info("Synced %s", ",".join(list(files)))
            if output:
                self.logger.info("\n%s", output)
            return True
        self.logger.warning("runSync %s\n%s\n%s", files, " ".join(cmd), output)
        return False

parser = argparse.ArgumentParser(description="SUNRISE Cruise syncing")
MyLogger.addArgs(parser)
Pusher.addArgs(parser)
parser.add_argument("dir", nargs="+", type=str, help="Directory tree(s) to monitor")
parser.add_argument("--noInitial", action="store_true", help="Don't do an initial full sync")

args = parser.parse_args()

logger = MyLogger.mkLogger(args)

logger.info("args %s", args)

try:
    inotify = MyInotify.MyInotify(args, logger)
    pusher = Pusher(inotify.queue, args, logger)

    for item in args.dir:
        inotify.addTree(item)

    if not args.noInitial:
        pusher.runSync(set(args.dir))

    inotify.start()
    pusher.start()

    MyThread.waitForException() # Wait for any errors from the threads
except:
    logger.exception("Unexpected exception")
