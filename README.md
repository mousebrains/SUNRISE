# SUNRISE Cruise Related Scripts

Scripts for use during the 2021 SUNRISE Gulf of Mexico Cruise

The folling scripts are built to run on a Raspberry Pi on the ship and pushing/pulling data to/from a shore side server.

syncPush.py uses rsync to send files from local directories to a remote directory. The sync is triggered by inotify events.

syncPull.py uses rsync to pull files from a remote host to a local directory tree. The sync is triggered based on an elapsed time.

The following scripts are built to run on a shore side server.

Carthe.py pulls GPS fixes for the Carthe drifters and stores the data in an SQLITE3 database and a CSV file.

LiveViewGPS.py listens for UDP datagrams for the LiveViewGPS receivers. The data is stored in an SQLITE3 database and a CSV file.
