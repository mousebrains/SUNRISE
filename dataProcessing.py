#! /usr/bin/python3
#
# Recast Jamie's realtime.sh into python with full logging of all errors
#
# June-2021, Pat Welch, pat@mousebrains.com

import argparse
import MyLogger
import logging
import datetime
import subprocess
import os.path
import sys

def execItem(item:str, stime:datetime.datetime, etime:datetime.datetime,
        directory:str, prefix:str, suffix:str, logger:logging.Logger) -> bool:
    executable = os.path.join(prefix, item + suffix)
    if not os.path.isfile(executable):
        logger.error("executable, %s, is not a file", executable)
        return False

    cmd = ["/usr/bin/python3", executable, stime, etime, directory]
    logger.debug("Executing %s", " ".join(cmd))

    sp = subprocess.run(cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = sp.stdout
    if output:
        try:
            output = str(output, "UTF-8")
        except:
            pass

    if sp.returncode: # Non-zero return code
        logger.error("Error executing %s\n%s", " ".join(cmd), output)
        return False
    if output: # zero return code, but output
        logger.info("Output for %s\n%s", " ".join(cmd), output)
    return True

def parseDate(tString:str, logger:logging.Logger) -> datetime.datetime:
    try:
        return datetime.datetime.fromisoformat(tString)
    except:
        logger.exception("Error converting %s into a datetime, should be of the " + \
                "form 2021-09-21T22:33:44",
                tString)
        sys.exit(2)

parser = argparse.ArgumentParser()
MyLogger.addArgs(parser)
parser.add_argument("--start", type=str, required=True,
        help="Start date and time in UTC, 2021-09-21T11:21:34")
grp = parser.add_mutually_exclusive_group(required=True)
grp.add_argument("--end", type=str, help="Start date and time in UTC, 2021-09-21T11:21:34")
grp.add_argument("--dt", type=float, help="Length of interval in hours") 
parser.add_argument("--item", type=str, action="append", help="Items to process")

parser.add_argument("--overwrite", action="store_true", help="Overwrite existing results")
parser.add_argument("--prefix", type=str, default="/home/pat/SUNRISE/data_processing",
        help="Command directory for items to be executed")
parser.add_argument("--suffix", type=str, default=".py",
        help="Command file extension to be executed")
parser.add_argument("directory", type=str, help="Directory to write results into")
args = parser.parse_args()

if args.item is None:
    args.item = ("throughflow", "adcp_vectors", "adcp_sections")

logger = MyLogger.mkLogger(args)
logger.debug("args=%s", args)

if not args.overwrite and os.path.isdir(args.directory):
    logger.error("Directory, %s, already exists", args.directory)
    sys.exit(1)

stime = parseDate(args.start, logger)

if args.end is None:
    etime = stime + datetime.timedelta(seconds=args.dt * 3600);
else:
    etime = parseDate(args.end, logger)

stime = stime.isoformat()
etime = etime.isoformat()


for item in args.item:
    if not execItem(item, stime, etime, args.directory, args.prefix, args.suffix, logger): break

sys.exit(0)
