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
import os.path

class Pull:
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        self.args = args
        self.logger = logger
        cmd = [
                args.rsync,
                "--compress",
                "--compress-level=22",
                "--archive",
                "--mkpath",
                "--relative",
                "--copy-unsafe-links",
                "--delete",
                "--stats",
                ]

        if args.remote is not None:
            cmd.extend(["--rsync-path", args.remote])

        if args.bwlimit is not None: 
            cmd.extend(["--bwlimit", str(args.bwlimit)])

        self.__cmd = cmd

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group(description="Shore side host related options")
        grp.add_argument("--host", type=str, default="vm3",
                help="Target machine to pull information from")
        grp.add_argument("--rsync", type=str, default="/usr/bin/rsync",
                help="Rsync command to use")
        grp.add_argument("--remote", type=str, default="bin/mkFiles.py",
                help="--rsync-path argument")

        grp = parser.add_argument_group(description="Pulling related options")
        grp.add_argument("--src", choices=["rvp", "rvws"], required=True,
                help="Which ship to fetch sources for, R/V Pelican or R/V Walton Smith")
        grp.add_argument("--prefix", type=str, default="Dropbox",
                help="Where the timestamp file lives")
        grp.add_argument("--dest", type=str, default=".", help="Local folder to rsync into")
        grp.add_argument("--bwlimit", type=int, default=200, help="KB/sec to pull data")
        grp.add_argument("--dryrun", action="store_true", help="Don't actually run rsync command")

    def execute(self) -> bool:
        args = self.args
        logger = self.logger
        tsName = os.path.join(args.dest, args.prefix, args.src + ".timestamp")
        tMax = 0
        self.logger.info("tsName=%s", tsName)
        try:
            with open(tsName, "r") as fp:
                self.logger.info("opened tsName=%s", tsName)
                tMax = float(fp.read())
        except Exception as e:
            tMax = 0

        cmd = self.__cmd.copy()
        cmd.append(args.host + ":" + args.src + "." + str(tMax))
        cmd.append(args.dest)

        logger.info("CMD: %s", cmd)

        if args.dryrun:
            return True

        sp = subprocess.run(args=cmd,
                shell=False,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
        output = sp.stdout
        try:
            output = str(output, "utf-8")
        except:
            pass
        if sp.returncode == 0:
            if len(output):
                logger.info("Sync output\n%s", output)
            return True
        logger.warning("execute failed for\n%s", output)
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
