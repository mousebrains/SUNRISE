#
# Install NGINX configuration file
#
# June-2021, Pat Welch, pat@mousebrains.com

NGINXUSER = pat

NGINXDIR = /etc/nginx
AVAILDIR = $(NGINXDIR)/sites-available
ENABLDIR = $(NGINXDIR)/sites-enabled

FPMCONF = /etc/php/7.4/fpm/pool.d/www.conf

.PHONY: install

install: $(AVAILDIR)/sunrise

$(AVAILDIR)/sunrise: sunrise
	sudo cp $< $@
	sudo ln -sf $@ $(ENABLDIR)
	sudo rm -f $(ENABLDIR)/default
	sudo sed -e s/www-data/$(NGINXUSER)/ --in-place=.orig $(NGINXDIR)/nginx.conf
	sudo nginx -t
	sudo sed -e s/www-data/$(NGINXUSER)/ --in-place=.orig $(FPMCONF)
	sudo systemctl restart nginx php7.4-fpm
