#
# Install services and executables in the appropriate spots
# June-2021, Pat Welch, pat@mousebrains.com

SYSDIR = /etc/systemd/system
LOGSDIR = $(HOME)/logs
DROPDIR = $(HOME)/Dropbox/Shore/Drifter

ITEMS = Carthe LiveViewGPS
SERVICES = $(ITEMS:%=$(SYSDIR)/%.service)

.PHONY: install clean status restart stop enable disable

install: $(SERVICES)

clean: stop disable
	sudo $(RM) $(SERVICES)

$(SYSDIR)/%.service: $(LOGSDIR) $(DROPDIR)

$(SYSDIR)/%.service: %.service
	sudo cp $< $@
	sudo systemctl daemon-reload
	sudo systemctl enable $<
	sudo systemctl restart $<

$(LOGSDIR) $(DROPDIR):
	mkdir -p $@

status:
	systemctl --no-pager $@ $(ITEMS)

restart stop enable disable:
	sudo systemctl $@ $(ITEMS)
