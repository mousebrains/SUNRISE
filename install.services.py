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
import socket
import sys

def discoverByHostname(args:argparse.ArgumentParser) -> None:
    hostname = socket.gethostname() # Get this comptuer's hostname
    if hostname == "glidervm3":
        args.shore = True
        args.primary = False
        args.secondary = False
    elif hostname == "pelican0":
        args.pelican = True
        args.primary = True
        args.secondary = False
    elif hostname == "pelican1":
        args.pelican = True
        args.primary = False
        args.secondary = True
    elif hostname == "waltonsmith0":
        args.waltonsmith = True
        args.primary = True
        args.secondary = False
    elif hostname == "waltonsmith1":
        args.waltonsmith = True
        args.primary = False
        args.secondary = True
    elif hostname == "pi4":
        args.pi4 = True
        args.primary = True
        args.secondary = False
    elif hostname == "pi5":
        args.pi4 = True
        args.primary = False
        args.secondary = True
    else:
        print("Unrecognized hostname,", hostname)
        sys.exit(1)

    opts = []
    if args.shore: opts.append("--shore")
    if args.pelican: opts.append("--pelican")
    if args.waltonsmith: opts.append("--waltonsmith")
    if args.pi4: opts.append("--pi4")
    if args.primary: opts.append("--primary")
    if args.secondary: opts.append("--secondary")
    print("Discovered options:", " ".join(opts))

def execCmd(args:tuple, qIgnoreReturn:bool=False) -> bool:
    sp = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)

    if sp.returncode:
        print("Failure while executing, {}:".format(sp.returncode))
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

    if not qIgnoreReturn and sp.returncode:
        sys.exit(sp.returncode)

    return True

def execSystemctl(cmd:str, services:list=None, qIgnoreReturn:bool=False) -> bool:
    systemctl = "/usr/bin/systemctl"
    items = [systemctl, cmd]
    if services is not None: items.extend(services)
    return execCmd(items, qIgnoreReturn=qIgnoreReturn)

def copyService(src:str, service:str) -> bool:
    cpCmd = "/usr/bin/cp"
    dest = os.path.join("/etc/systemd/system", service + ".service")
    return execCmd((cpCmd, src, dest))

def statusServices(services:tuple[str], dt:float=5) -> bool:
    if dt is not None:
        print("Waiting", dt, "seconds for services to start")
        time.sleep(dt)
    return execSystemctl("status", services)

def enableServices(services:tuple[str]) -> bool:
    execSystemctl("enable", services)
    execSystemctl("restart", services)

def disableServices(services:tuple[str]) -> bool:
    execSystemctl("stop", services, qIgnoreReturn=True)
    execSystemctl("disable", services)

def shoreInstall() -> None:
    services = (
            "Carthe", 
            "LiveViewGPS", 
            "Monitor", 
            "shipMonitor", 
            "Trigger",
            "positionHarvester",
            )
    for service in services: copyService(f"{service}.service", service)

    execSystemctl("daemon-reload")
    enableServices(services)
    statusServices(services)

def shipInstall(name:str, qPrimary:bool) -> None:
    services = ["syncPush", "syncPull"] # Named services
    services.append("syncLocal") # Sync to my local backup server
    services.append("Trigger") # Trigger plot generation on section files being created
    services.append("positionHarvester") # Harvest GPS fixes and store them in Processed

    for service in services:
        src = f"{service}.{name}.service"
        copyService(src, service)

    monServices = ["monitorPi"]
    for service in monServices: # Unnamed services
        copyService(service + ".service", service)

    execSystemctl("daemon-reload")

    if qPrimary: # Start the services
        enableServices(services)
    else:
        disableServices(services)

    enableServices(monServices) # Always running
    services.extend(monServices) # All services to check the status of
    statusServices(services)

parser = argparse.ArgumentParser()
grp = parser.add_mutually_exclusive_group(required=True)
grp.add_argument("--discover", action="store_true", help="Use hostname to decide what to do")
grp.add_argument("--waltonsmith", "--ws", action="store_true",
        help="Services for the R/V Walton Smith")
grp.add_argument("--pelican", action="store_true", help="Services for the R/V Pelican")
grp.add_argument("--shore", action="store_true", help="Services for the shore side server")
grp.add_argument("--pi4", action="store_true", help="Services for the test pi4")
grp = parser.add_mutually_exclusive_group(required=False)
grp.add_argument("--primary", action="store_true", help="This is a primary server")
grp.add_argument("--secondary", action="store_true", help="This is a secondary server")
args = parser.parse_args()

if args.discover: # Use hostname to set arguments
    discoverByHostname(args)

if args.shore:
    if args.primary or args.secondary:
        parser.error("You can not specify --primary nor --secondary with --shore")
else:
    if not args.primary and not args.secondary:
        parser.error("You must specify --primary or --secondary " + \
                "with --waltonsmith, --pelican or --pi4")

if args.shore:
    shoreInstall()
else:
    name = "WaltonSmith" if args.waltonsmith else "Pelican" if args.pelican else "pi4"
    shipInstall(name, args.primary)
