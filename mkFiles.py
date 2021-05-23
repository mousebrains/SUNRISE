#! /usr/bin/python3
#
# This generates a dynamic file list then invokes rsync
#
# It is designed to be called by a remote rsync client, 
# The last argument is the directory set, rvp or rvwm, 
# a period, then a floating point number which is the 
# timestamp to look for files which have been updated
# since that timestamp.
#
# The goal is to deal with a thin and flakey Internet
# connection from a ship to shore.
#
# May-2021, Pat Welch

import os
import sys
import sqlite3
import logging
import logging.handlers

logName = "/home/pat/logs/rsync.log"
smtpHost = "mail.ceoas.oregonstate.edu"
emailFrom = "pat.welch@oregonstate.edu"
emailTo = "pat@mousebrains.com"
subject = "ERROR shore sync"

dbName = "/home/pat/logs/Monitor.db"
tblName = "inotify" # Table to access in dbName

prefix = "Dropbox" # Parent directory

dirSets = { # What to send to the different ships
        "rvp": ("Shore", "WaltonSmith"), # R/V Pelican gets Shore +  R/V Walton Smith
        "rvws": ("Shore", "Pelican"), # R/V Walton Smith get Short + R/V Pelican
        }

rsync = "/usr/bin/rsync"

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

ch = logging.handlers.RotatingFileHandler(logName, maxBytes=1000000, backupCount=3)
ch.setLevel(logging.DEBUG)
ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
logger.addHandler(ch)

ch = logging.handlers.SMTPHandler(smtpHost, emailFrom, emailTo, subject)
ch.setLevel(logging.ERROR)
logger.addHandler(ch)


try:
    logger.info("%s", sys.argv)

    cmd = [rsync] # What rsync sees in argv
    cmd.extend(sys.argv[1:-1]) # Copy verbatim the rsync server options from the client

    # The last argument tells us what to look up, 
    # rvp.7576.222 is the key into dirSets, and a timestamp to parse out of the Monitor database
    #
    fields = sys.argv[-1].split(".", 1) # Get the last argument and split it apart
    if len(fields) != 2:
        raise Exception("Not enough fields in last argument, {}, {}".format(sys.argv[-1], fields))

    (keyArg, timestamp) = fields
    if keyArg not in dirSets:
        raise Exception("Unrecognized keyArg {}".format(keyArg))

    try:
        timestamp = float(timestamp)
    except:
        raise Exception("Error converting {} to a float".format(timestamp))

    criteria = []
    for item in dirSets[keyArg]:
        criteria.append("path LIKE '{}%'".format(os.path.join(prefix, item)))
    criteria = " WHERE t>? AND (" + " OR ".join(criteria) + ");"

    tsName = os.path.join(prefix, keyArg + ".timestamp")

    with sqlite3.connect(dbName) as db:
        cur = db.cursor()
        cur.execute("SELECT MAX(t),count(*) FROM " + tblName + criteria, (timestamp,))
        (tMax, cnt) = cur.fetchone()
        if tMax is not None:
            logger.info("tMax %s cnt %s", tMax, cnt)
            tMax = float(tMax)
            cnt = int(cnt)
            logger.info("keyArg %s tMax=%s cnt=%s", keyArg, tMax, cnt)
            if (timestamp <= 0) or (cnt > 50): # Too many individual files, so grab everything
                for item in dirSets[keyArg]:
                    cmd.append(os.path.join(prefix, item))
            else: # Grab the files that are newer than timestamp
                cur.execute("SELECT path,t FROM " + tblName + criteria, (timestamp,))
                tMax = 0
                for (path, t) in cur:
                    cmd.append(path)
                    tMax = max(tMax, t)

        cmd.append(tsName)

    if tMax is not None:
        with open(tsName, "w") as fp:
            fp.write("{}\n".format(tMax))

    logger.info("CMD: %s", cmd)
    os.execv(rsync, cmd)
except:
    logger.exception("Unexpected error")
    sys.exit(-1)
