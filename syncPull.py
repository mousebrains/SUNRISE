#! /usr/bin/python3
#
# Sync a set of folders from a another machine,
#
# May-2021, Pat Welch, pat@mousebrains.com

import logging
import argparse
import MyLogger
import time
import subprocess

class Pull:
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        self.__logger = logger
        cmd = [
                args.rsync,
                "--compress",
                "--compress-level=9",
                "--archive",
                "--mkpath",
                "--copy-unsafe-links",
                "--delete",
                ]
        if args.bwlimit is not None: 
            cmd.append("--bwlimit={:d}".format(args.bwlimit))

        for src in args.src:
            cmd.append(args.host + ":" + args.prefix + "/" + src)

        cmd.append(args.dest)
        self.__cmd = cmd
        logger.info("cmd\n%s", " ".join(self.__cmd))

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group(description="Host related options")
        grp.add_argument("--host", type=str, default="vm3",
                help="Target machine to push/pull information from/to")
        grp.add_argument("--prefix", type=str, default="Dropbox",
                help="Path prefix on host machine")
        grp.add_argument("--rsync", type=str, default="/usr/bin/rsync",
                help="Rsync command to use")

        grp = parser.add_argument_group(description="Pulling related options")
        grp.add_argument("--src", type=str, action="append", required=True,
                help="Folder(s) to pull from the host")
        grp.add_argument("--dest", type=str, default="dropbox", help="Folder to rsync into")
        grp.add_argument("--bwlimit", type=int, default=200, help="KB/sec to pull data")

    def execute(self) -> bool:
        sp = subprocess.run(args=self.__cmd, 
                shell=False,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
        if sp.returncode == 0:
            self.__logger.info("Synced")
            return True
        try:
            output = str(sp.stdout, "utf-8")
        except:
            output = sp.stdout
        self.__logger.warning("execute failed for\n%s\n%s", " ".join(self.__cmd), output)
        return False

parser = argparse.ArgumentParser(description="SUNRISE Cruise syncing")
MyLogger.addArgs(parser)
Pull.addArgs(parser)

parser.add_argument("--dt", type=float, default=600, help="Seconds between pull attempts")
parser.add_argument("--retry", type=int, default=60,
                help="Seconds between retries when pulling fails")
args = parser.parse_args()

logger = MyLogger.mkLogger(args)

logger.info("args %s", args)

puller = Pull(args, logger)

while True:
    dt = args.dt
    try:
        if not puller.execute():
            dt = args.retry # Failed, so try in this many seconds
    except:
        logger.exception("Unknown exception while pulling")
    logger.info("Sleeping for %s seconds", dt)
    time.sleep(dt) # Sleep this many seconds
