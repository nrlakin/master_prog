from pexpect import fdpexpect, TIMEOUT, run
from time import sleep
import os
import re

N_SLAVES = 1
RETRIES = 5

def connect():
    child = fdpexpect.fdspawn(os.open("/dev/ttyMFD1", os.O_RDWR|os.O_NOCTTY))
    return child

def wakeup(child):
    sleep(0.2)
    result = child.expect(["login", TIMEOUT], timeout=1)
    if result != 0:
        child.sendline("\n")
    return result

def configure_wifi(child, network, password):


def login(child, nopass=True):
    child.sendline("root")
    child.expect("word:")
    if nopass:
        child.send("\n")
    else:
        child.sendline("onemm@rga")

if __name__=="__main__":
    try:
        log = open("logfile", 'w')
        run('stty -F /dev/ttyMFD1 115200')
        child = connect()
        child.logfile=log
        asleep = 1
        while asleep == 1:
            asleep=wakeup(child)
        nopass = "edison" in child.before
        login(child, nopass)
        child.expect("#")
        print child.before
        child.close()
    except Exception as e:
        log.write(str(e))
        log.close()
        child.close()
# for slave in range(N_SLAVES):
#     log_name = "setup_log_slave_" + str(slave+1) + ".log"
#     f = open(log_name, 'w')
#     child = pexpect.spawn("/bin/sh")
#     child.logfile = f
#     for retry in RETRIES:
#         try:
#             child.sendline("\n")
#             result = child.expect(":")
#         except TimeoutException:
#             pass


# print("\n")
#
# print("configure_edison --wifi\n")
# print("1\n")  # manually enter network
# print("Kinetic\n")  # network name.
# print("Y\n")        # confirm network name
# print("2\n")        # security type = WPA-Personal
# print("00deadbeef\n") # network password
#
# print("wget --no-check-certificate http://neil-lakin.com/download/init_firmware.sh -P /tmp || exit 1\n")
# print("chmod a+x /tmp/init_firmware.sh\n")
