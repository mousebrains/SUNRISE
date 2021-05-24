# SUNRISE Cruise Related Scripts

Scripts for use during the **2021 SUNRISE Gulf of Mexico** Cruise

# Ship side scripts for the Raspberry Pis
There are two ships involve, the R/V Pelican and the R/V Walton Smith.

The scripts running on each include:
1. *syncPush.py* which is invoked by one of the *syncPush.service* systemctl services.
*syncPush.py* uses an inotify monitoring mechanism to be notified whenever anything changes
in their directory tree, for example *~/Dropbox/WaltonSmith* for the R/V Walton Smith.
10 seconds after the notice is seen, anything that is seen is pushed to 
the shore side server via *rsync*.
2. *syncPull.py*  which is invoked by one of the *syncPull.service* systemctl services.
*syncPull.py* periodically requests a sync from the shore side server.
It does this via *rsync* with a custom **--rsync_path** option to invoke the shore side
script *mkFiles.py*. See below for a description of *mkFiles.py*.

# Shore side scripts

The scripts running on the shore side server include:
1. *Monitor.py* which uses an inotify monitoring mechanism to be notified whenever anything changes
in a directory tree. By default it is monitor *~/Dropbox*.
All changes, and their time stamp are recorded in a database for use by *mkFiles.py*.
This script is invoked by the Monitor.service systemctl service.
2. *mkFiles.py* is invoked by the ship side script, *syncPull.py*.
It queries the *Monitor.py* generated database to determine which files have changed since the
previous call by the ship side script.
The files to be transferred are dynamically built on the server side.
3. *Carthe.py* is invoked by the *Carthe.service* systemctl service.
It periodically pulls GPS fixes from the **Pacific Gyre** **API** 
and stores them in the *Carthe.db* database.
It also generates a **CSV** file which is stored in the shore side folder for syncing to the ships.
4. *LiveViewGPS.py* is invoked by the *LiveViewGPS.service* systemctl service.
It is listening on port 6565:UDP for datagrams with GPS fixes from LiveViewGPS.
The fixes are stored in the *LiveViewGPS.db* database.
It also generates a **CSV** file which is stored in the shore side folder for syncing to the ships.
