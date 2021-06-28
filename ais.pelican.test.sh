#! /usr/bin/bash -x
#
# Run AIS2.py on the Pelican collecting raw AIS datagrams for further testing.
#
# June-2021, Pat Welch, pat@mousebrains.com

DT=1800

# MYDIR=pi4
MYDIR=Pelican

RAW=/home/pat/Processed/AIS/ais.raw.db
DROPDIR=/home/pat/Dropbox/$MYDIR/AIS

/usr/bin/mkdir -p  `dirname $RAW` $DROPDIR
/home/pat/SUNRISE/AIS2.py \
	--logfile=$DROPDIR/ais.test.log \
	--raw=$RAW \
	--dt=$DT \
	&& \
	/usr/bin/cp $RAW $DROPDIR \
	2>&1 >$DROPDIR/ais.output
	
