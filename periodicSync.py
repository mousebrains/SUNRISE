#! /usr/bin/python3
#
# Wake up periodically and push a directory tree to a target, and pull from target.
# This was built to facilitate the Cruise Report, so everything is in one directory tree.
#
# July-2021, Pat Welch

import argparse
import os.path
import time
import MyLogger
import logging
import subprocess


def rsync(cmd:list[str], logger:logging.Logger) -> None:
    sp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
    if sp.returncode not in [0, 24, 25]:
        if sp.stdout:
            try:
                logger.warning("Failed(%s) executing %s\%s",
                        sp.returncode, cmd, str(sp.stdout, "utf-8"))
            except:
                logger.warning("Failed(%s) executing %s\%s", sp.returncode, cmd, sp.stdout)
    elif sp.stdout:
        try:
            logger.info("%s\n%s", " ".join(cmd), str(sp.stdout, "utf-8"))
        except:
            logger.info("%s\n%s", " ".join(cmd), sp.stdout)

parser = argparse.ArgumentParser()
MyLogger.addArgs(parser)
parser.add_argument("--tempdir", type=str, default="/home/pat/rsync.temp",
        help="Where to write temporary files to before moving them into place")
parser.add_argument("--root", type=str, default="/home/pat/Dropbox/CruiseReport",
        help="Root of tree to work on")
parser.add_argument("--pushdir", type=str, required=True, help="My directory to push")
parser.add_argument("--hostname", type=str, default="vm3", help="hostname to push/pul to/from")
parser.add_argument("--bwPush", type=int, help="Bandwidth limit while pushing")
parser.add_argument("--bwPull", type=int, help="Bandwidth limit while pulling")
parser.add_argument("--dt", type=float, default=600, help="Delay between syncing")
args = parser.parse_args()

logger = MyLogger.mkLogger(args)
logger.info("args %s", args)

preCmd = ["/usr/bin/rsync"]
preCmd.append("--stats")
preCmd.append("--archive")
preCmd.append("--delete")
if args.tempdir is not None: preCmd.extend(["--temp-dir", args.tempdir])

pushCmd = list(preCmd)
pullCmd = list(preCmd)

if args.bwPush is not None: pushCmd.extend(["--bwlimit", str(args.bwPush)])
pushCmd.append(os.path.join(args.root, args.pushdir))
pushCmd.append(args.hostname + ":" + args.root)

if args.bwPull is not None: pushCmd.extend(["--bwlimit", str(args.bwPull)])
pullCmd.extend(["--exclude", args.pushdir])
pullCmd.append(args.hostname + ":" + args.root)
pullCmd.append(args.root)

while True:
    try:
        rsync(pullCmd, logger)
    except:
        logger.exception("Error pulling %s", " ".join(pullCmd))
    try:
        rsync(pushCmd, logger)
    except:
        logger.exception("Error pushing %s", " ".join(pushCmd))
    logger.info("Sleepign for %s seconds", args.dt)
    time.sleep(args.dt)
