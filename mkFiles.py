#! /usr/bin/python3
#
# This generates a dynamic file list then invokes rsync
#
# It is designed to be called by a remote rsync client,
# The last argument is the directory set, rvp rvws, or rvpi4,
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

commonDirs = ["Shore", "js", "css", "png", "maps", "html"] # Common to all dirSets

dirSets = { # What to send to the different ships
        "rvp": ["WaltonSmith"], # R/V Pelican gets Shore +  R/V Walton Smith
        "rvws": ["Pelican"], # R/V Walton Smith get Shore + R/V Pelican
        "rvpi4": ["Pelican", "WaltonSmith"], # pi4 get Shore+RVWS+RVPELICAN
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
    if "SSH_CONNECTION" in os.environ: logger.info("CONN: %s", os.environ["SSH_CONNECTION"])
    logger.info("CALL: %s", sys.argv)

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
    for item in dirSets[keyArg] + commonDirs:
        criteria.append("path LIKE '{}%'".format(os.path.join(prefix, item)))

    sql = "SELECT path,t FROM " + tblName
    sql+= " WHERE t>? AND (" + " OR ".join(criteria) + ")"
    sql+= ";"

    tsName = os.path.join(prefix, keyArg + ".timestamp")

    with sqlite3.connect(dbName) as db:
        tMax = timestamp
        toAdd = set() # Retain unique paths incase we climb a directory tree
        toDirs = set() # Directory elements sorted by length
        cur = db.cursor()
        cur.execute(sql, (timestamp,))
        for (path, t) in cur: # Walk through returned rows
            tMax = max(tMax, t)
            if not os.path.exists(path): # Climb directory tree until we find an existing element
                origPath = path # For an error message if need be
                while len(path): # Walk up the tree
                    path = os.path.dirname(path) # remove last element
                    if os.path.exists(path): # Found an existing parent directory
                        toDirs.add(path) # I know this is a directory
                        toAdd.add(path)
                        break
                if len(path) == 0:
                    logger.error("No existing element found for %s", origPath)
            else: # Exists
                toAdd.add(path)
                if os.path.isdir(path):
                    toDirs.add(path)

    keepDirs = set()
    for item in sorted(toDirs, key=len):
        path = item
        while len(path) and (path not in keepDirs):
            path = os.path.dirname(path)
        if len(path) == 0:
            keepDirs.add(item)

    keepAdd = set()
    for item in toAdd:
        path = item
        while len(path) and (path not in keepDirs):
            path = os.path.dirname(path)
        if len(path) == 0:
            keepAdd.add(item)
        else: # Not zero, so in keepDirs
            keepAdd.add(path)

    if len(keepAdd) > 100: # Too many, so resync everything
        keepAdd = set()
        for item in dirSets[keyArg]:
            keepAdd.add(os.path.join(prefix, item))

    if keepAdd:
        cmd.extend(keepAdd)

    cmd.append(tsName) # Always sync the timestamp file

    if tMax > timestamp:
        with open(tsName, "w") as fp:
            fp.write("{}\n".format(tMax))

    logger.info("CMD: %s", cmd)
    os.execv(rsync, cmd)
except:
    logger.exception("Unexpected error")
    sys.exit(-1)
