# Create MicroSD card with Ubuntu server
# Ubuntu 21.04 ARM 64bit server
# login in to the default user, ubuntu with password ubuntu
# login into ubuntu@IP ADDR
# change ubuntu password
# login using new password

# Fully update the server
sudo apt update
sudo apt upgrade
sudo reboot

# login back in using ubuntu and your password

# Install fail2ban
sudo apt install fail2ban

# Install acl support
sudo apt install acl

# Disable automatic updates and upgrades
# in /etc/apt/apt.conf/20auto-upgrades change both "1" fields to "0"

# Set the hostname

# For MAC dc:a6:32:8b:d1:16 -> Walton Smith primary machine
sudo hostnamectl set-hostname waltonsmith0 # MAC dc:a6:32:8b:d1:16 sunrise0
# For MAC dc:a6:32:8b:cf:07 -> Walton Smith backup machine
sudo hostnamectl set-hostname waltonsmith1 # MAC dc:a6:32:8b:cf:07 sunrise1
# For MAC dc:a6:32:8b:cf:fc -> Pelican primary machine
sudo hostnamectl set-hostname pelican0 # MAC dc:a6:32:8b:cf:fc sunrise2
# For MAC dc:a6:32:8b:cf:6c -> Pelican backup machine
sudo hostnamectl set-hostname pelican1 # MAC dc:a6:32:8b:cf:6c sunrise3

# Enable zeroconf/bonjour via AVAHI-DAEMON
sudo apt install avahi-daemon

# Add a sunrise group
sudo addgroup sunrise

# Create sudo user pat
sudo adduser pat
sudo usermod -aG sudo pat
sudo usermod -aG sunrise pat
# logout
# login as pat

# Remove user ubuntu
sudo deluser --remove-home ubuntu

# Create Dropbox and logs folder
mkdir -p Dropbox logs

# Create ssh config file for vm3 in ~/.ssh/config, it should contain:
Host vm3 glidervm3 glidervm3.ceoas.oregonstate.edu
  Hostname glidervm3.ceoas.oregonstate.edu
  User pat
  IdentityFile ~/.ssh/id_rsa
  Compression yes

# Create ssh key pair for talking to glidervm3 and install it on glidervm3
ssh-keygen -b2048
ssh-copy-id -i ~/.ssh/id_rsa.pub vm3

# Initial sync from vm3
rsync --archive --compress --compress-level=22 --mkpath --copy-unsafe-links --delete-missing-args --delete --relative --stats vm3:Dropbox/ .

# Set up ACL for my home directory and Dropbox
setfacl --modify=group:sunrise:rX . Dropbox
setfacl --recursive --modify=group:sunrise:rwX Dropbox/*

# Install webserver, NGINX, and PHP
sudo apt install nginx php-fpm
cd /etc/nginx/sites-available
sudo cp default sunrise
# Edit sunrise and change 
# root to /home/pat/Dropbox 
# uncomment php lines for fastcgi_pass
# add index.php to index
# add "autoindex on;" to the location stanza
cd ../sites-enabled
sudo rm default
sudo ln -s /etc/nginx/sites-available/sunrise .
cd ..
# edit nginx.conf and change the user from www-data to pat
sudo nginx -t
# Edit /etc/php/7.4/fpm/pool.d/www.conf and change www-data to pat for both
# user, group, listen.owner, and listen.group
sudo systemctl restart nginx php7.4-fpm

# Install SAMBA for smb mounting for the ASVs
sudo apt install samba*
# Create the mount point if it does not exist
mkdir /home/pat/Dropbox/WaltonSmith/asv
# Add the mount point into the samba config file /etc/samba/smb.conf
#
# For all machines:
# [Dropbox]
#   comment = "Sunrise Dropbox Folder
#   path = /home/pat/Dropbox
#   browseable = yes
#   read only = yes
#   guest ok = yes
#
# For the Walton Smith machines
#
# [ASV]
#   comment = SUNRISE ASV folders
#   path = /home/pat/Dropbox/WaltonSmith/ASV
#   browseable = yes
#   readonly = no 
#
# Create the SMB user with a known password, Sunrise
sudo smbpasswd -a pat
sudo systemctl restart smbd

# Install required python packages
sudo apt install python3-pip
python3 -m pip install inotify-simple

# Set up git
git config --global user.name "Pat Welch"
git config --global user.email pat@mousebrains.com
git config --global core.editor vim
git config --global pull.rebase false
git clone git@github.com:mousebrains/SUNRISE.git

# Install services using hostname discovery method

cd ~/SUNRISE
sudo ./install.services.py --discover

# To add a user use ~/SUNRISE/addUser this sets up the groups ...

# Setup ssh for key only for OSU, take these out and restart sshd
sudo rm /etc/ssh/sshd_config.d/osu_security.conf
sudo rm /etc/ssh/banner.txt
sudo rm /etc/motd
sudo systemctl restart sshd
