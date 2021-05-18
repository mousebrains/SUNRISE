# SUNRISE Cruise Related Scripts

Scripts for use during the 2021 SUNRISE Gulf of Mexico Cruise

syncPush.py uses rsync to send files from local directories to a remote directory. The sync is triggered by inotify events.

syncPull.py uses rsync to pull files from a remote host to a local directory tree. The sync is triggered based on an elapsed time.
