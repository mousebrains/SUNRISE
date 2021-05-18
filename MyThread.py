#
# Base class for threading which catches exceptions and sends them to a queue
#
# Feb-2020, Pat Welch, pat@mousebrains.com

import logging
import queue
import threading

class MyThread(threading.Thread):
    def __init__(self, name:str, logger:logging.Logger, q:queue.Queue) -> None:
        threading.Thread.__init__(self, daemon=True)
        self.name = name
        self.logger = logger
        self.q = q

    def run(self) -> None: # Called on thread start
        try:
            self.runIt() # Call the actual class's run function inside a try
        except Exception as e:
            self.q.put(e)
