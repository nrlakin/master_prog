from pexpect import fdpexpect, TIMEOUT, run, spawn
from time import sleep
import os
import sys
import re

N_SLAVES = 3
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
    child = spawn("/usr/bin/screen /dev/ttyMFD1 115200 -L",
        maxread=1,
        timeout=25,
        searchwindowsize=100,
        echo=False
        )
    # child.logfile_read = sys.stdout
    child.delaybeforesend = 0.5
    return child

def wakeup(child):
    sleep(0.2)
    child.send("\n")
    result = child.expect(["login", TIMEOUT])
    return result

def start_boot(child):
    child.sendline("wget --no-check-certificate http://neil-lakin.com/download/init_firmware.sh")
    child.expect(":~#")
    child.sendline("chmod a+x init_firmware.sh")
    child.expect(":~#")
    child.sendline("./init_firmware.sh")
    child.expect("edison-image-edison.ext4")

def configure_wifi(child, network='Kinetic', password='00deadbeef'):
    child.sendline('configure_edison --wifi')
    child.expect('SSIDs:')
    opts = child.before.split('\n')
    option = '1'
    for item in opts:
        if "Manually input" in item:
            option = item[0]
            break;
    child.sendline(option)
    child.expect('network SSID:')
    child.sendline(network)
    child.expect("[Y or N]:")
    child.sendline("Y")
    child.expect("Select the type of security[0 to 3]":)
    child.sendline("2")
    child.expect("password")
    child.sendline(password)

def login(child, nopass=True):
    child.sendline("root")
    child.expect("word:")
    if nopass:
        child.send("\n")
    else:
        child.sendline("onemm@rga")

if __name__=="__main__":
    print("Initializing UART1.")
    out = run('stty -F /dev/ttyMFD1 115200 -parenb -parodd cs8 hupcl -cstopb cread clocal -crtscts -ignbrk -brkint -ignpar -parmrk -inpck -istrip -inlcr -igncr -icrnl -ixon -ixoff -iuclc -ixany -imaxbel iutf8 opost -olcuc -ocrnl onlcr -onocr -onlret -ofill -ofdel nl0 cr0 tab0 bs0 vt0 ff0 -isig -icanon -iexten -echo -echoe -echok -echonl -noflsh -xcase -tostop -echoprt -echoctl -echoke')
    print("Initializing GPIOs.")
    initGPIOs()
    for slave in range(N_SLAVES):
        try:
            print("Configuring Slave %d." % (slave+1))
            setSlave(slave+1)
            print("Creating logfile.")
            log = open("init_slave_"+str(slave+1)+".log", 'w')
            print("Creating connection to slave.")
            child = connect()
            child.logfile=log
            print("Trying to wake slave.")
            asleep = 1
            for retry in range(RETRIES):
                print "Try: " + str(retry)
                asleep=wakeup(child)
                if asleep == 0:
                    break
            if asleep == 1:
                print("Couldn't wake slave %d. Moving on..." % (slave+1))
                log.write("Couldn't wake slave %d. Moving on...\n" % (slave+1))
                raise ValueError
            nopass = "edison" in child.before
            print("Slave awake, logging in as root.")
            login(child, nopass)
            child.expect(":~#")
            print("We're in! Configuring wifi...")
            configure_wifi(child)
            child.expect(":~#")
            print("Wifi configured. Downloading files and initializing ota update.")
            start_boot(child)
            # print child.before
            child.close()
            log.close()
        except Exception as e:
            log.write(str(e))
            child.close()
            log.close()
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
