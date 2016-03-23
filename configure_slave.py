from pexpect import fdpexpect, TIMEOUT, run, spawn
from time import sleep
import os
import sys
import re

N_SLAVES = 1
RETRIES = 5

SEL0 = 47
SEL1 = 48
SEL2 = 49
SEL3 = 15
SELECTS = [SEL3, SEL2, SEL1, SEL0]

PINSTATES = {   '1': [0, 0, 0, 0],
                '2': [0, 0, 0, 1],
                '3': [0, 0, 1, 0],
                '4': [0, 0, 1, 1],
                '5': [0, 1, 0, 0],
                '6': [0, 1, 0, 1],
                '7': [0, 1, 1, 0],
                '8': [0, 1, 1, 1],
                '9': [1, 0, 0, 0],
                '10': [1, 0, 0, 1]}


def initGPIOs():
    term = spawn("/bin/sh")

    cmd = "echo 128 > /sys/class/gpio/export"
    term.sendline(cmd)
    cmd = "echo mode0 > /sys/kernel/debug/gpio_debug/gpio128/current_pinmux"
    term.sendline(cmd)
    cmd = "echo high > sys/class/gpio/gpio128/direction"
    term.sendline(cmd)

    cmd = "echo 129 > /sys/class/gpio/export"
    term.sendline(cmd)
    cmd = "echo mode0 > /sys/kernel/debug/gpio_debug/gpio129/current_pinmux"
    term.sendline(cmd)
    cmd = "echo high > sys/class/gpio/gpio129/direction"
    term.sendline(cmd)

    cmd = "echo 130 > /sys/class/gpio/export"
    term.sendline(cmd)
    cmd = "echo mode1 > /sys/kernel/debug/gpio_debug/gpio130/current_pinmux"
    term.sendline(cmd)

    cmd = "echo 131 > /sys/class/gpio/export"
    term.sendline(cmd)
    cmd = "echo mode1 > /sys/kernel/debug/gpio_debug/gpio131/current_pinmux"
    term.sendline(cmd)

    for gpio in SELECTS:
        cmd = "echo "+str(gpio)+" > /sys/class/gpio/export"
        print cmd
        term.sendline(cmd)
        if gpio == SEL0 or gpio == SEL3:
            cmd = "echo mode0 > /sys/kernel/debug/gpio_debug/gpio"+str(gpio)+"/current_pinmux"
            print cmd
            term.sendline(cmd)
        cmd = "echo out > /sys/class/gpio/gpio"+str(gpio)+"/direction"
        print cmd
        term.sendline(cmd)
        cmd = "echo "+str(0)+" > /sys/class/gpio/gpio"+str(gpio)+"/value"
        print cmd
        term.sendline(cmd)
    term.close()

def setSlave(slavenum = 1):
    try:
        pins = PINSTATES[str(slavenum)]
    except Exception as e:
        print str(e)
    term = spawn("/bin/sh")
    for index, value in enumerate(pins):
        sel = SELECTS[index]
        cmd = "echo "+str(value)+" > /sys/class/gpio/gpio"+str(sel)+"/value"
        print cmd
        term.sendline(cmd)
    term.close()

def connect():
    child = fdpexpect.fdspawn(os.open("/dev/ttyMFD1",
        os.O_RDWR|os.O_NONBLOCK|os.O_NOCTTY),
        logfile=sys.stdout,
        delaybeforesend=0.4,
        maxread=1,
        timeout=2,
        searchwindowsize=100,
        echo=False
        )
    child.logfile_read = sys.stdout
    return child

def wakeup(child):
    sleep(0.2)
    result = child.expect(["login", TIMEOUT])
    if result != 0:
        child.sendline("\n")
    return result

def configure_wifi(child, network='Kinetic', password='00deadbeef'):
    child.sendline('configure_edison --wifi')
    child.expect('')
    return True

def login(child, nopass=True):
    child.sendline("root")
    child.expect("word:", timeout=-1)
    if nopass:
        child.send("\n")
    else:
        child.sendline("onemm@rga")

if __name__=="__main__":
    try:
        print("Initializing GPIOs.")
        initGPIOs()
        print("Creating logfile.")
        log = open("logfile", 'w')
        print("Initializing UART1.")
        out = run('stty -F /dev/ttyMFD1 115200 -parenb -parodd cs8 hupcl -cstopb cread clocal -crtscts -ignbrk -brkint -ignpar -parmrk -inpck -istrip -inlcr -igncr -icrnl -ixon -ixoff -iuclc -ixany -imaxbel iutf8 opost -olcuc -ocrnl onlcr -onocr -onlret -ofill -ofdel nl0 cr0 tab0 bs0 vt0 ff0 -isig -icanon -iexten -echo -echoe -echok -echonl -noflsh -xcase -tostop -echoprt -echoctl -echoke')
        print("Creating connection to slave.")
        child = connect()
        # child.logfile=log
        print("Trying to wake slave.")
        asleep = 1
        for retry in range(RETRIES):
            print "Try: " + str(retry)
            asleep=wakeup(child)
            if asleep == 0:
                break
        if asleep == 1:
            raise ValueError
        nopass = "edison" in child.before
        login(child, nopass)
        child.expect("#")
        # print child.before
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
