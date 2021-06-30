#! /usr/bin/env python3
#
# Use inotify_simple to interface to the glibc version of inotify
#
# this handles setting up and taking down directory watches on the
# full directory tree
#

import argparse
import MyThread
import inotify_simple as ins
import logging
import os
import time
import queue
import re

class MyInotify(MyThread.MyThread):
    def __init__(self, args:argparse.ArgumentParser, logger:logging.Logger):
        MyThread.MyThread.__init__(self, "INotify", args, logger)
        self.queue = queue.Queue()
        self.__mapping = {}
        self.__inotify = ins.INotify()
        self.__flags = ins.flags.CREATE \
                | ins.flags.MODIFY \
                | ins.flags.CLOSE_WRITE \
                | ins.flags.MOVED_TO \
                | ins.flags.MOVED_FROM \
                | ins.flags.MOVE_SELF \
                | ins.flags.DELETE \
                | ins.flags.DELETE_SELF
    
    def __repr__(self) -> str:
        items = []
        for key in self.__mapping:
            items.append("{} -> {}".format(key, self.__mapping[key]))
        return "\n".join(items)

    def __addWatch(self, dirName:str) -> None:
        wd = self.__inotify.add_watch(dirName, self.__flags)
        self.__mapping[wd] = dirName
        self.logger.debug("add %s %s", wd, dirName)

    def __rmTree(self, root:str) -> None:
        inotify = self.__inotify
        logger = self.logger
        toDrop = []
        for key in self.__mapping:
            if re.match(r"^" + root + r"(|/)$", self.__mapping[key]):
                logger.debug("Removing %s %s", key, self.__mapping[key])
                toDrop.append(key)
                try:
                    inotify.rm_watch(key)
                except OSError: # No watched dir for the wd
                    pass
        if toDrop: # Separate loop so dictionary is not changing on us
            for key in toDrop:
                del self.__mapping[key]

    def addTree(self, root:str) -> None:
        inotify = self.__inotify
        # Recursively walk through root's directory tree and add watches to each directory
        for (dirpath, dirnames, filenames) in os.walk(root):
            self.__addWatch(dirpath) # os.walk will hit all the dirnames too, so skip here

    def runIt(self) -> None: # Called on thread start
        inotify = self.__inotify
        items = self.__mapping
        logger = self.logger
        q = self.queue
        logger.info("Starting")
        while True:
            events = inotify.read()
            t0 = time.time()
            files = set()
            toDelete = set()
            toAdd = set()
            try:
                for event in events:
                    wd = event.wd
                    if (wd not in items):
                        if not (event.mask & ins.flags.IGNORED):
                            logger.warning("Missing wd for %s", event)
                        continue
                    path = items[wd] if event.name == "" else os.path.join(items[wd], event.name)
                    files.add(path)
                    logger.debug("event wd=%s name=%s %s %s", wd, event.name, path,
                            ",".join(map(str, ins.flags.from_mask(event.mask))))

                    if event.mask & ins.flags.DELETE_SELF:
                        toDelete.add(path)
                    elif (event.mask & ins.flags.ISDIR) and (event.mask & ins.flags.CREATE):
                        toAdd.add(path)
                    elif (event.mask & ins.flags.ISDIR) and (event.mask & ins.flags.MOVED_FROM):
                        toDelete.add(path)
                    elif (event.mask & ins.flags.ISDIR) and (event.mask & ins.flags.MOVED_TO):
                        toAdd.add(path)
                    elif event.mask & ins.flags.MOVE_SELF:
                        toDelete.add(path) # Delete myself and children
                if files:
                    q.put(("FILES", t0, files))

                if toDelete:
                    q.put(("DELETE", t0, toDelete))
                    for item in toDelete:
                        for item in toDelete:
                            self.__rmTree(item)

                if toAdd: 
                    for item in toAdd:
                        self.addTree(item)
                    q.put(("ADD", t0, toAdd)) # Send after new watches are added
            except:
                logger.exception("GotMe")

if __name__ == "__main__":
    import MyLogger

    parser = argparse.ArgumentParser()
    MyLogger.addArgs(parser)
    parser.add_argument("dirs", nargs='+', type=str, help="directories to watch")
    args = parser.parse_args()

    logger = MyLogger.mkLogger(args)
    try:
        inotify = MyInotify(args, logger)

        for item in args.dirs:
            inotify.addTree(item)

        inotify.start() # Start the thread
        logger.info("isQueueEmpty %s", MyThread.isQueueEmpty())
        while MyThread.isQueueEmpty():
            logger.info("Looping")
            try:
                info = inotify.queue.get(timeout=60)
                inotify.queue.task_done()
                logger.info("info %s", info)
            except queue.Empty:
                pass

        MyThread.waitForException() # There should be something here
    except:
        logger.exception("Unexpected exception")
        
