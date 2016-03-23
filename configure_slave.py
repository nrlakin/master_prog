from pexpect import fdpexpect
import os
import re

N_SLAVES = 1
RETRIES = 5

def connect():
    child = fdpexpect.fdspawn(os.open("/dev/ttyMFD1", os.O_RDWR|os.O_NONBLOCK|os.O_NOCTTY))
    return child

def wakeup(child):
    child.sendline("\n")
    return child.expect(["login:", pexpect.TIMEOUT], timeout=1)

def login(child, nopass=True):
    child.sendline("root")
    child.expect("word:")
    if nopass:
        child.send("\n")
    else:
        child.sendline("onemm@rga")

if __name__=="__main__":
    child = connect()
    asleep = 1
    while asleep == 1:
        asleep=wakeup(child)
    nopass = "edison" in child.before
    login(child, nopass)
    child.expect("#")
    print child.before
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
