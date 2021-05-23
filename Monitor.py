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
import MyInotify
import MyThread
import logging
import argparse
import sqlite3
import os.path
import queue
import time

class Monitor(MyThread.MyThread):
    def __init__(self, queue:queue.Queue,
            args:argparse.ArgumentParser, logger:logging.Logger) -> None:
        MyThread.MyThread.__init__(self, "MON", args, logger)
        self.__queue = queue
        self.__mkTable()

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        parser.add_argument("--db", type=str, default="inotify.db", help="File database")
        parser.add_argument("--table", type=str, default="inotify", help="Database table name")

    def __mkTable(self) -> None:
        tbl = self.args.table
        index = tbl + "_t"
        self.__sqlInsert = "INSERT OR REPLACE INTO " + tbl + " VALUES(?,?);"
        sql = "CREATE TABLE " + tbl + " (\n"
        sql+= "  path TEXT PRIMARY KEY,\n"
        sql+= "  t REAL\n"
        sql+= " );"
        self.logger.info("Creating table\n%s", sql)
        with sqlite3.connect(self.args.db) as db:
            cur = db.cursor()
            cur.execute("BEGIN;")
            cur.execute("DROP INDEX IF EXISTS " + index + ";")
            cur.execute("DROP TABLE IF EXISTS " + tbl + ";")
            cur.execute(sql)
            cur.execute("CREATE INDEX " + index + " ON " + tbl + " (t);")
            cur.execute("COMMIT;")

    def __insertItem(self, cur:sqlite3.Cursor, path:str, mtime:float=None) -> None:
        if mtime is None:
            if os.path.exists(path):
                mtime = os.path.getmtime(path)
            else:
                mtime = time.time() # File was probably deleted or moved
        cur.execute(self.__sqlInsert, (path, mtime))

    def __addFiles(self, t:float, names:set) -> None:
        with sqlite3.connect(self.args.db) as db:
            cur = db.cursor()
            cur.execute("BEGIN;")
            for name in names:
                self.__insertItem(cur, name, t)
            cur.execute("COMMIT;")

    def __addDirs(self, t:float, names:set) -> None:
        with sqlite3.connect(self.args.db) as db:
            cur = db.cursor()
            cur.execute("BEGIN;")
            for name in names:
                for (dirpath, dirnames, filenames) in os.walk(name):
                    self.__insertItem(cur, dirpath, t)
                    for fn in filenames:
                        self.__insertItem(cur, os.path.join(dirpath, fn), t)
            cur.execute("COMMIT;")

    def addTree(self, root:str, t:float=None) -> None:
        with sqlite3.connect(self.args.db) as db:
            cur = db.cursor()
            cur.execute("BEGIN;")
            for (dirpath, dirnames, filenames) in os.walk(root):
                # dirnames will be walked over into a dirpath, so no need to add dirnames
                self.__insertItem(cur, dirpath, t)
                for fn in filenames:
                    self.__insertItem(cur, os.path.join(dirpath, fn), t)
            cur.execute("COMMIT;")

    def runIt(self) -> None: # Called on thread start
        q = self.__queue
        logger = self.logger
        logger.info("Starting")
        while True:
            (action, t, names) = q.get()
            q.task_done()
            logger.info("action %s t %s names %s", action, t, names)
            if (action == "FILES") or (action == "DELETE"):
                self.__addFiles(t, names)
            elif action == "ADD":
                self.__addDirs(t, names)
            else:
                logger.error("Unrecognized action %s", action)

parser = argparse.ArgumentParser()
MyLogger.addArgs(parser)
Monitor.addArgs(parser)
parser.add_argument("dir", nargs="+", type=str, help="Directory trees to monitor")
args = parser.parse_args()

logger = MyLogger.mkLogger(args)
logger.info("args=%s", args)

try:
    inotify = MyInotify.MyInotify(args, logger)
    monitor = Monitor(inotify.queue, args, logger)
    
    for item in args.dir:
        inotify.addTree(item)
        monitor.addTree(item)

    inotify.start()
    monitor.start()
    
    MyThread.waitForException()
except:
    logger.exception("Unexpected exception")
