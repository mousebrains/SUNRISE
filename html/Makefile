# Install the files here in the appropriate spot
#
# June-2021, Pat Welch, pat@mousebrains.com

ROOTDIR = ~/Dropbox
HTMLDIR = $(ROOTDIR)/html

.PHONY: install mainIndex

install: mainIndex

mainIndex: $(ROOTDIR) $(HTMLDIR) $(HTMLDIR)/index.main.php $(ROOTDIR)/index.php

$(ROOTDIR)/index.php: $(HTMLDIR)/index.main.php
	ln -sf $< $@

$(HTMLDIR)/index.main.php: index.main.php
	cp $< $@


$(ROOTDIR) $(HTMLDIR):
	mkdir -p $@
