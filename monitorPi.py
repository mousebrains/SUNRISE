#! /usr/bin/python3
#
# Record the temperature and disk space into a CSV file periodically
#
# May-2021, Pat Welch, pat@mousebrains.com

import MyLogger
import logging
import argparse
import socket
import time
import json
import os

def postData(hostname:str, args:argparse.ArgumentParser, logger:logging.Logger) -> None:
    data = bytearray()
    data+= (0x0123).to_bytes(2, byteorder="big", signed=False)
    data+= int(time.time() - args.tOffset).to_bytes(4, byteorder="big")
    logger.info("t %s %s", time.time(), time.time() - args.tOffset)
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as fp:
            temp = int(fp.read()) / 1000
            logger.info("Temperature %s", temp)
            data+= int(temp * args.tempNorm).to_bytes(2, byteorder="big", signed=True)
    except:
        data+= (0xffff).to_bytes(2, byteorder="big", signed=True)

    try:
        info = os.statvfs(args.fs)
        norm = info.f_frsize / 2**30 # tens of gigabytes
        total = info.f_blocks * norm
        free = info.f_bavail * norm
        used = (info.f_blocks - info.f_bfree) * norm
        logger.info("Total %s free %s used %s GB", total, free, used)
        data+= int(free * args.spaceNorm).to_bytes(2, byteorder="big", signed=False)
        data+= int(used * args.spaceNorm).to_bytes(2, byteorder="big", signed=False)
    except:
        data+= (0xffff).to_bytes(2, byteorder="big", signed=False)
        data+= (0xffff).to_bytes(2, byteorder="big", signed=False)

    data+= len(hostname).to_bytes(2, byteorder="big", signed=False)
    data+= hostname

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        n = s.sendto(data, (args.host, args.port))
        logger.info("host %s port %s sent %s bytes of %s", args.host, args.port, n, len(data))
        
parser = argparse.ArgumentParser()
MyLogger.addArgs(parser)
parser.add_argument("--tOffset", type=int, default=1622346500,
        help="Subtracted from current time before being sent")
parser.add_argument("--tempNorm", type=float, default=100, help="multiple sent temperature by this")
parser.add_argument("--spaceNorm", type=float, default=100, help="multiple sent used/free by this")
parser.add_argument("--fs", type=str, default="/", help="Filesystem to send information about")
parser.add_argument("--dt", type=float, default=600, help="Time between samples")
parser.add_argument("--host", type=str, required=True, help="Hostname to send datagrams to")
parser.add_argument("--port", type=int, default=11113, help="port to send datagrams to")
args = parser.parse_args()

logger = MyLogger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")

try:
    hostname = bytes(socket.gethostname(), "UTF-8")
    while True:
        postData(hostname, args, logger)
        logger.info("Sleeping for %s seconds", args.dt)
        time.sleep(args.dt)
except:
    logger.exception("Unexpected exception")
