#
# Read a datagram and send to a set of queus
#
# May-2021, Pat Welch, pat@mousebrains.com

import socket
import time
import argparse
import logging
from MyThread import MyThread

class Reader(MyThread):
    ''' Wait on a queue, and write the item to a file '''
    def __init__(self, args:argparse.ArgumentParser, queues:list, logger:logging.Logger) -> None:
        MyThread.__init__(self, "Reader", args, logger)
        self.queues = queues
        self.port = args.port
        self.size = args.size

    @staticmethod
    def addArgs(parser:argparse.ArgumentParser) -> None:
        grp = parser.add_argument_group(description="UDP Listener options")
        grp.add_argument('--port', type=int, required=True, metavar='port', help='Port to listen on')
        grp.add_argument("--size", type=int, default=65536, help="Datagram size")

    def runAndCatch(self) -> None:
        '''Called on thread start '''
        queues = self.queues
        logger = self.logger
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            logger.debug("Opened UDP socket")
            s.bind(('', self.port))
            logger.info('Bound to port %s', self.port)
            while True: # Read datagrams
                (data, senderAddr) = s.recvfrom(self.size)
                t = time.time()
                logger.info("Received from %s\n%s", senderAddr, data)
                for q in queues: q.put((t, senderAddr, data))
