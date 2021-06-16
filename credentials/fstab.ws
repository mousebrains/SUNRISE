LABEL=writable	/	 ext4	discard,errors=remount-ro	0 1
LABEL=system-boot       /boot/firmware  vfat    defaults        0       1
//nas1.local/GOM	/mnt/GOM cifs rw,credentials=/home/pat/SUNRISE/credentials/ws.smbcredentials,vers=2.0,noperm,uid=1001,gid=1001 0 0
//nas1.local/UHdas	/mnt/UHdas cifs ro,credentials=/home/pat/SUNRISE/credentials/ws.smbcredentials,vers=2.0,noperm,uid=1001,gid=1001 0 0
