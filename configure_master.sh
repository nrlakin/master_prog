echo "Upgrading opkg repositories...\n"
echo src/gz all http://repo.opkg.net/edison/repo/all > /etc/opkg/base-feeds.conf
echo src/gz edison http://repo.opkg.net/edison/repo/edison >> /etc/opkg/base-feeds.conf
echo src/gz core2-32 http://repo.opgk.net/edison/repo/core2-32 >> /etc/opkg/base-feeds.conf
opkg update
echo "Upgrading existing installs...\n"
opkg upgrade
echo "Installing Python...\n"
opkg install python-devel
echo "Trying opkg pip...\n"
opkg install python-pip
opkg "Pulling get-pip.py...\n"
wget --no-check-certificate https://bootstrap.pypa.io/get-pip.py
echo "Installing up-to-date pip...\n"
python get-pip.py
echo "Installing pexpect...\n"
pip install pexpect
echo "Installing screen...\n"
opkg install screen
echo "Rebooting...\n"
reboot
