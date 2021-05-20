#! /usr/bin/env python3
#
# Set up an inotify watcher on some directories,
# then populate a database with the results.
#
# Initially populate the database with the last modification
# times of the full tree.
#
# May-2021, Pat Welch, pat@mousebrains.com

import MyLogger
import logging
import argparse
import sqlite3
import inotify_simple as ins
import os
import time

def mkTable(cur:sqlite3.Cursor, tblName:str, logger:logging.Logger) -> None:
    sql = "CREATE TABLE " + tblName
    sql+= " ("
    sql+= "  top TEXT,"
    sql+= "  fn TEXT,"
    sql+= "  t REAL,"
    sql+= "  PRIMARY KEY(top, fn)"
    sql+= " );"
    logger.info("Creating table\n%s", sql)
    cur.execute("DROP TABLE IF EXISTS " + tblName + ";")
    cur.execute(sql)

def insertItem(cur:sqlite3.Cursor, sql:str, topName:str, fn:str) -> None:
    mtime = os.path.getmtime(fn)
    path = os.path.relpath(fn, topName)
    cur.execute(sql, (topName, path, mtime))

def walkTree(cur:sqlite3.Cursor, sql:str, topName:str, logger:logging.Logger) -> None:
    for (dirpath, dirnames, filenames) in os.walk(topName):
        for fn in filenames:
            insertItem(cur, sql, topName, os.path.join(dirpath, fn))
        for fn in dirnames:
            insertItem(cur, sql, topName, os.path.join(dirpath, fn))

parser = argparse.ArgumentParser()
MyLogger.addArgs(parser)
parser.add_argument("--db", type=str, default="inotify.db", help="File database")
parser.add_argument("--table", type=str, default="inotify", help="Database table name")
parser.add_argument("dir", nargs="+", help="Directories to watch")
args = parser.parse_args()

logger = MyLogger.mkLogger(args)

try:
    inotify = ins.INotify()
    wd = {}
    flags = ins.flags.CREATE \
            | ins.flags.MODIFY \
            | ins.flags.CLOSE_WRITE \
            | ins.flags.MOVED_TO \
            | ins.flags.MOVED_FROM \
            | ins.flags.MOVE_SELF \
            | ins.flags.DELETE \
            | ins.flags.DELETE_SELF
    for src in args.dir:
        wd[inotify.add_watch(os.path.abspath(src), flags)] = src
except:
    logger.exception("Error building inotify watchers")

# We're watching the directories, so we'll catch any actions 
# that happen while rebuilding the database.
# But now empty, then fully populate the database by scanning the entire
# directory tree.
#
sql = "INSERT OR REPLACE INTO " + args.table + " VALUES(?,?,?);"
try:
    with sqlite3.connect(args.db) as db:
        cur = db.cursor()
        cur.execute("BEGIN;")
        mkTable(cur, args.table, logger)
        for src in args.dir:
            walkTree(cur, sql, src, logger)
        cur.execute("COMMIT;")
except:
    logger.exception("Error walking directory trees")

try:
    while True:
        for event in inotify.read(): # Wait for an inotify event, then read it
            t = time.time()
            path = os.path.join(wd[event.wd], event.name)
            with sqlite3.connect(args.db) as db:
                topName = wd[event.wd]
                fn = os.path.join(topName, event.name)
                logger.info("top %s fn %s", topName, fn)
                cur = db.cursor()
                cur.execute("BEGIN;")
                insertItem(cur, sql, topName, fn)
                cur.execute("COMMIT;")
except:
    logger.exception("Error waiting on inotify events")
