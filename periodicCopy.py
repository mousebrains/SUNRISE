#! /usr/bin/python3
#
# Wake up periodically and copy a file to a new location, if it has changed size.
# If only the timestamp has changed, then calculate a signature and if that is
# different, then copy it.
#
# There can be multiple target locations, but only one temporary directory
#
# July-2021, Pat Welch

import argparse
import os
import time
from tempfile import NamedTemporaryFile
import MyLogger
import logging
import sys

def qCopy(src:str, mtime:int, logger:logging.Logger) -> bool:
    if not os.path.exists(src):
        logger.warning("File %s does not exist", src)
        return False

    if mtime is None: return True

    try:
        t = os.stat(src).st_mtime
        return t != mtime
    except:
        logger.exception("Unable to get status for %s", src)
        return False

def mkCopy(src:str, targets:list, tempdir:str, chunksize:int, logger:logging.Logger) -> int:
    mtime = None
    try:
        ofps = []
        names = []
        for tgt in targets: 
            ofps.append(NamedTemporaryFile(delete=False, 
                dir=os.path.dirname(tgt) if tempdir is None else tempdir, 
                mode="wb", ))
            names.append(ofps[-1].name)
        logger.info("names %s", names)

        with open(src, "rb") as ifp:
            mtime = os.fstat(ifp.fileno()).st_mtime
            sz = 0
            while True:
                data = ifp.read(chunksize)
                if not data: break # EOF
                sz += len(data)
                for ofp in ofps: ofp.write(data)
            logger.info("Read %s bytes from %s", sz, src)

        for i in range(len(targets)):
            os.fchmod(ofps[i].fileno(), 0o664)
            ofps[i].close()
            try:
                os.replace(names[i], targets[i])
                logger.info("Copied %s to %s", names[i], targets[i])
            except:
                logger.exception("Error copying %s to %s", names[i], targets[i])
                try:
                    os.remove(names[i]) # Get rid of temporary file
                except:
                    logger.exception("Error removing %s", names[i])
        return mtime
    except:
        logger.exception("Error in mkCopy %s %s %s %s", src, targets, tempdir, chunksize)
    return None


def doit(args:argparse.ArgumentParser, logger:logging.Logger) -> None:
    src = args.src
    targets = args.tgt
    tempdir = args.tempdir
    chunksize = args.chunksize
    dtLong = max(10, args.dtLong)
    dtShort = max(1, args.dtShort)

    mtime = None

    while True:
        if not os.path.exists(src): # Wait for the file to appear/reappear
            logger.info("%s does not exist, sleeping for %s seconds", src, dtLong)
            time.sleep(dtLong)
            mtime= None
            continue

        dt = dtShort
        if qCopy(src, mtime, logger):
            try:
                mtime = mkCopy(src, targets, tempdir, chunksize, logger)
                if mtime is not None:
                    dt = max(10, dtLong - (time.time() - mtime))
            except:
                logger.exception("Trying to copy %s to %s temp %s", src, targets, tempdir)
                mtime = None
                dt = dtLong
        logger.info("sleeping for %s seconds", dt)
        time.sleep(dt)

parser = argparse.ArgumentParser()
MyLogger.addArgs(parser)
parser.add_argument("--tempdir", type=str,
        help="Where to write temporary files to before moving them into place")
parser.add_argument("--src", type=str, required=True,
        help="Source filename to monitor for changes")
parser.add_argument("--tgt", type=str, required=True, action="append",
        help="Target directory(s) to copy file into")
parser.add_argument("--dtLong", type=float, default=300,
        help="Expected period between updates in seconds between polling for file changes")
parser.add_argument("--dtShort", type=float, default=30,
        help="Short delay while waiting for an update in seconds")
parser.add_argument("--chunksize", type=int, default=1024*1024,
        help="How many bytes to read at a time")
args = parser.parse_args()

logger = MyLogger.mkLogger(args)
logger.info("args %s", args)

for tgt in args.tgt:
    dirname = os.path.dirname(tgt)
    if not os.path.isdir(dirname):
        logger.error("%s is not a directory", dirname)
        sys.exit(1)
    if os.path.isdir(tgt):
        logger.error("%s is a directory", tgt)
        sys.exit(2)

if (args.tempdir is not None) and (not os.path.isdir(args.tempdir)):
    try:
        os.makedirs(args.tempdir, mode=0o775, exist_ok=True)
        logger.info("Made %s", args.tempdir)
    except:
        logger.exception("Error creating %s", args.tempdir)
        args.tempdir = None

try:
    doit(args, logger)
except:
    logger.exception("Error processing copy")
    sys.exit(1)
