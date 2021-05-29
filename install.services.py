#! /usr/bin/env python3
#
# Install services for one of the
#   R/V Walton Smith
#   R/V Pelican
#   Shore side server
#
# This script should be run as sudo to install files in /etc/systemd/system
# and to manipulate systemctl
#
# May-2021, Pat Welch

import argparse
import os.path
import subprocess
import time
import sys

def execCmd(args:tuple) -> bool:
    sp = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)

    if sp.returncode:
        print("Failure while executing:")
        print(args)
    else:
        print(" ".join(args))

    if sp.stdout:
        output = sp.stdout
        try:
            output = str(output, "utf-8")
        except:
            pass
        print(output)

    if sp.returncode:
        sys.exit(sp.returncode)

    return True

def execSystemctl(cmd:str, services:list=None) -> bool:
    systemctl = "/usr/bin/systemctl"
    items = [systemctl, cmd]
    if services is not None: items.extend(services)
    return execCmd(items)

def shoreInstall() -> None:
    print("Shore side not implemented yet!")
    sys.exit(1)

def shipInstall(name:str, qPrimary:bool) -> None:
    prefix = "/etc/systemd/system"
    suffix = ".service"
    cpCmd = "/usr/bin/cp"
    services = []
    for key in ["Push", "Pull"]:
        service = "sync" + key
        services.append(service)
        src = f"{service}.{name}{suffix}"
        dest = os.path.join(prefix, f"{service}{suffix}")
        execCmd((cpCmd, src, dest))

    execSystemctl("daemon-reload")

    if qPrimary: # Start the services
        execSystemctl("enable", services)
        execSystemctl("restart", services)
        dt = 5
        print("Waiting", dt, "seconds for services to start")
        time.sleep(dt)
    else:
        execSystemctl("disable", services)

    execSystemctl("status", services)

parser = argparse.ArgumentParser()
grp = parser.add_mutually_exclusive_group(required=True)
grp.add_argument("--waltonsmith", "--ws", action="store_true",
        help="Services for the R/V Walton Smith")
grp.add_argument("--pelican", action="store_true", help="Services for the R/V Pelican")
grp.add_argument("--shore", action="store_true", help="Services for the shore side server")
grp = parser.add_mutually_exclusive_group(required=False)
grp.add_argument("--primary", action="store_true", help="This is a primary server")
grp.add_argument("--secondary", action="store_true", help="This is a secondary server")
args = parser.parse_args()

if args.shore:
    if args.primary or args.secondary:
        parser.error("You can not specify --primary nor --secondary with --shore")
else:
    if not args.primary and not args.secondary:
        parser.error("You must specify --primary or --secondary with --waltonsmith or --pelican")

if args.shore:
    shoreInstall()
else:
    shipInstall("WaltonSmith" if args.waltonsmith else "Pelican", args.primary)
