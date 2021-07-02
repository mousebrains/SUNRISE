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
    if args.hostname is None:
        hostname = socket.gethostname() # Get this comptuer's hostname
        args.hostname = hostname
    else:
        hostname = args.hostname

    if hostname == "glidervm3":
        args.shore = True
        args.primary = False
        args.secondary = False
        args.syncLocal = False
    elif hostname == "pelican0" or hostname == "pelicanais":
        args.pelican = True
        args.primary = False
        args.secondary = True
        args.syncLocal = False
    elif hostname == "pelican1":
        args.pelican = True
        args.primary = True
        args.secondary = False
        args.syncLocal = True
    elif hostname == "waltonsmith0":
        args.waltonsmith = True
        args.primary = True
        args.secondary = False
        args.syncLocal = True
    elif hostname == "waltonsmith1":
        args.waltonsmith = True
        args.primary = False
        args.secondary = True
        args.syncLocal = False
    elif hostname == "pi4":
        args.pi4 = True
        args.primary = True
        args.secondary = False
        args.syncLocal = True
    elif hostname == "pi5":
        args.pi4 = True
        args.primary = False
        args.secondary = True
        args.syncLocal = False
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
    if args.syncLocal: opts.append("--syncLocal")
    print("Discovered options:", " ".join(opts))

def execCmd(cmd:tuple, args:argparse.ArgumentParser, qIgnoreReturn:bool=False) -> bool:
    if args.dryrun:
        print("Not going to run", cmd)
        return True

    sp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)

    if sp.returncode:
        print("Failure while executing, {}:".format(sp.returncode))
        print(cmd)
    else:
        print(" ".join(cmd))

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

def execSystemctl(cmd:str, args:argparse.ArgumentParser, services:list=None, qIgnoreReturn:bool=False) -> bool:
    systemctl = "/usr/bin/systemctl"
    items = [systemctl, cmd]
    if services is not None: items.extend(services)
    return execCmd(items, args, qIgnoreReturn=qIgnoreReturn)

def copyService(src:str, service:str, args:argparse.ArgumentParser) -> bool:
    cpCmd = "/usr/bin/cp"
    dest = os.path.join("/etc/systemd/system", service + ".service")
    return execCmd((cpCmd, src, dest), args)

def statusServices(services:tuple[str], args:argparse.ArgumentParser, dt:float=5) -> bool:
    if dt is not None:
        print("Waiting", dt, "seconds for services to start")
        time.sleep(dt)
    return execSystemctl("status", args, services)

def enableServices(services:tuple[str], args:argparse.ArgumentParser) -> bool:
    execSystemctl("enable", args, services)
    execSystemctl("restart", args, services)

def disableServices(services:tuple[str], args:argparse.ArgumentParser) -> bool:
    execSystemctl("stop", args, services, qIgnoreReturn=True)
    execSystemctl("disable", args, services)

def shoreInstall(args:argparse.ArgumentParser) -> None:
    services = (
            "Carthe", 
            "LiveViewGPS", 
            "Monitor", 
            "shipMonitor", 
            "Trigger",
            # "positionHarvester",
            "asvDigest",
            "wirewalker",
            )
    for service in services: copyService(f"{service}.service", service, args)

    execSystemctl("daemon-reload", args)
    enableServices(services, args)
    statusServices(services, args)

def shipInstall(name:str, args:argparse.ArgumentParser) -> None:
    special = {} # Ship specific services
    special["waltonsmith0"] = ["asvDigest"]
    special["waltonsmith1"] = special["waltonsmith0"]
    special["Pelican"] = ["PelicanMidasCopy", "wh300Copy", "wh600Copy", "wh1200Copy"]
    special["WaltonSmith"] = ["wh600Copy", "wh1200Copy"]

    services = ["syncPush", "syncPull"] # Named services
    if args.syncLocal: services.append("syncLocal") # Sync to my local backup server
    services.append("Trigger") # Trigger plot generation on section files being created
    services.append("positionHarvester") # Harvest GPS fixes and store them in Processed
    services.append("asvDigest") # Harvest ASV store it in Processed
    services.append("AIS") # Harvest GPS fixes and store them in Processed
    services.append("AIS") # Harvest GPS fixes and store them in Processed

    if name in special: services.extend(special[name])

    for service in services:
        src = f"{service}.{name}.service"
        copyService(src, service, args)

    monServices = ["monitorPi"]
    for service in monServices: # Unnamed services
        copyService(service + ".service", service, args)

    execSystemctl("daemon-reload", args)

    if args.primary: # Start the services
        enableServices(services, args)
    else:
        disableServices(services, args)

    enableServices(monServices, args) # Always running
    services.extend(monServices) # All services to check the status of
    statusServices(services, args)

parser = argparse.ArgumentParser()
grp = parser.add_mutually_exclusive_group(required=True)
grp.add_argument("--discover", action="store_true", help="Use hostname to decide what to do")
grp.add_argument("--waltonsmith", "--ws", action="store_true",
        help="Services for the R/V Walton Smith")
grp.add_argument("--pelican", action="store_true", help="Services for the R/V Pelican")
grp.add_argument("--shore", action="store_true", help="Services for the shore side server")
grp.add_argument("--pi4", action="store_true", help="Services for the test pi4")
grp.add_argument("--hostname", type=str, help="don't use gethostname")
grp = parser.add_mutually_exclusive_group(required=False)
grp.add_argument("--primary", action="store_true", help="This is a primary server")
grp.add_argument("--secondary", action="store_true", help="This is a secondary server")
grp.add_argument("--syncLocal", action="store_true", 
        help="Enable syncing from the primary server to the secondary server")
parser.add_argument("--dryrun", action="store_true", help="Don't actually do anything.")
args = parser.parse_args()

if args.discover or args.hostname: # Use hostname to set arguments
    discoverByHostname(args)

if args.shore:
    if args.primary or args.secondary:
        parser.error("You can not specify --primary nor --secondary with --shore")
else:
    if not args.primary and not args.secondary:
        parser.error("You must specify --primary or --secondary " + \
                "with --waltonsmith, --pelican or --pi4")

if args.shore:
    shoreInstall(args)
else:
    name = "WaltonSmith" if args.waltonsmith else "Pelican" if args.pelican else "pi4"
    shipInstall(name, args)
