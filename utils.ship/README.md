# A collection of utilities for use on the ship side servers
- Turn on/off services:
  - `turnOff` turns off all pushing/pulling services. This is the state of the backup server normally.
  - `turnOnBackup` turns on pushing/pulling services to shore, but not to the backup server. This is what one would do if the primary server breaks and you want the backup server to become replace it.
  - `turnOnPrimary` turns on pushing/pulling services to shore and the backpu server. This should not be needed.
- `makeTunnel` sets up a ssh tunnel from the shore side server to the ship server so a shore side person can log into the ship side server.

