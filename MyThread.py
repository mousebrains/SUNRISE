#
# Base class for threading which catches exceptions and sends them to a queue
#
# Feb-2020, Pat Welch, pat@mousebrains.com

import logging
import queue
from threading import Thread
from argparse import ArgumentParser

myQueue = queue.Queue()

def isQueueEmpty() -> bool:
    return myQueue.empty()

def waitForException(timeout=None):
    if timeout is None:
        e = myQueue.get()
        raise e
    try:
        e = myQueue.get(timeout=timeout)
        print(e)
    except queue.Empty:
        return
    except Exception as e:
        raise e

class MyThread(Thread):
    def __init__(self, name:str, args:ArgumentParser, logger:logging.Logger) -> None:
        Thread.__init__(self, daemon=True)
        self.name = name
        self.args = args
        self.logger = logger

    def run(self) -> None: # Called on thread start
        try:
            self.runIt() # Call the actual class's run function inside a try
        except Exception as e:
            myQueue.put(e)
