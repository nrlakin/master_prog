from pexpect import fdpexpect, TIMEOUT, run, spawn
from time import sleep
import os
import termios
import sys
import re

"""
Constants go up here.
"""
# Number of slave ports on dock.
N_SLAVES = 10

# Number of wakeup/login retries.
RETRIES = 3

# Remote file URLs
INIT_FIRMWARE_SH_URL = "http://neil-lakin.com/download/init_firmware.sh"
# Return values for wakeup()
WAKE_STATE_AWAKE = 0
WAKE_STATE_AWAKE_LOGGED_IN = 1
WAKE_STATE_ASLEEP = 2

# MUX Selection pins
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
    """
    Initialize select pins and UART 1. Also disables hardware flow control.
    Note that this function will briefly spawn a shell process.

    Args: None

    Returns: Nothing.
    """
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
        term.sendline(cmd)
        if gpio == SEL0 or gpio == SEL3:
            cmd = "echo mode0 > /sys/kernel/debug/gpio_debug/gpio"+str(gpio)+"/current_pinmux"
            term.sendline(cmd)
        cmd = "echo out > /sys/class/gpio/gpio"+str(gpio)+"/direction"
        term.sendline(cmd)
        cmd = "echo "+str(0)+" > /sys/class/gpio/gpio"+str(gpio)+"/value"
        term.sendline(cmd)
    term.close()
    print("Wait for new GPIO settings to take effect...")
    sleep(3)

def setSlave(slavenum = 1):
    """
    Set select pins to 'point' UART 1 at correct slave. Note that this function
    will briefly spawn a shell process.

    Args:
        slavenum (int): Number of slave to program. 1-10.

    Returns: Nothing.
    """
    try:
        pins = PINSTATES[str(slavenum)]
        print("    Setting select pins (SEL3:0 = %s)" % (':'.join([str(val) for val in pins])))
    except Exception as e:
        print str(e)
    term = spawn("/bin/sh")
    for index, value in enumerate(pins):
        sel = SELECTS[index]
        cmd = "echo "+str(value)+" > /sys/class/gpio/gpio"+str(sel)+"/value"
        term.sendline(cmd)
    term.close()
    print("    Wait for new GPIO settings to take effect...")
    sleep(3)

def printSelects():
    term = spawn("/bin/sh")
    for sel in SELECTS:
        cmd = "cat /sys/class/gpio/gpio"+str(sel)+"/value"
        term.sendline(cmd)
        result = term.readline()
        if "cat" in result:
            # echo enabled, discard
            result = term.readline()
        print("gpio %d: %s" % (sel, result))
    term.close()

def connect():
    """
    Create a connection to a slave device.

    Args: None

    Returns: Pexpect spawn object.
    """
    child = spawn("/usr/bin/screen /dev/ttyMFD1 115200",
        maxread=2000,
        timeout=5,
        searchwindowsize=100,
        echo=False
        )
    # child.logfile_read = sys.stdout
    child.delaybeforesend = 0.3
    return child

def wakeup(child):
    """
    Attempt to wake up a slave device.

    Args:
        child (Pexpect spawn object): Connection to slave.

    Returns:
        result (int):
            0 if slave is awake and awaiting login
            1 if slave is awake and already logged in
            2 if slave is not connected or still asleep (timeout)
    """
    sleep(0.2)
    child.send("\n")
    child.send("\n")
    result = child.expect(["login:", ":~#", TIMEOUT], timeout=5)
    return result

def start_boot(child):
    """
    Initialize firmware boot procedure. Fetch firmware init script from web,
    chmod it to executable, and run it. Breaks when it sees files downloading.

    Args:
        child (Pexpect spawn object): Connection to slave.

    Returns: Nothing
    """
    # script name should be last part of url.
    init_script_name = INIT_FIRMWARE_SH_URL.split('/')[-1]
    send_backspaces()
    print("    Downloading boot script.")
    child.sendline("wget --no-check-certificate " + INIT_FIRMWARE_SH_URL)
    child.expect(":~#", timeout=30)
    send_backspaces()   # make sure awake after download.
    print("    Setting to executable...")
    child.sendline("chmod a+x " + init_script_name)
    child.expect(":~#")
    print("    Executing...")
    child.sendline("./" + init_script_name)
    print("    On our way!")
    child.expect("edison-image-edison")

def send_backspaces():
    """
    Send some backspaces to keep UART alive. In some processes (like configuring
    wifi or setting password) sending newlines might interfere with output.

    Args: None

    Returns: Nothing
    """
    for i in range(5):
        child.send("\010")

def flush_uart():
    """
    Flush the serial connection. Flush the terminal file handler, and destroy
    active screen processes. This is extremely important--failing to do this
    results in corrupted reads on the incoming file with increasing bit errors
    on each new connection.

    Args: None

    Returns: Nothing
    """
    screens = run("screen -ls").split()
    for phrase in screens:
        if ".pts" in phrase:
            session = phrase.split(".")[0]
            print("    Killing active screen session %s" % (session.lstrip()))
            run("screen -S "+session.lstrip()+" -X kill")

def configure_wifi(child, network='Kinetic', password='00deadbeef'):
    """
    Configure wifi in slave device.

    Args:
        child (Pexpect spawn object): Connection to slave.
        network (string): Name of network to connect to. Defaults to 'Kinetic'.
        password (string): Password for network. Defaults to '00deadbeef'.

    Returns: Nothing
    """
    send_backspaces()   # make sure awake
    child.sendline('configure_edison --wifi')
    result = child.expect(['SSIDs:','SSID:'], timeout=30)
    # Different boards have a different response; some versions present a list,
    # some fresh edisons just ask for a '1'.
    if result == 1:
        option = '1'
    else:
        opts = child.before.split('\n')
        option = '1'
        for item in opts:
            if "Manually input" in item:
                option = item[0]
                break;
    child.sendline(option)
    child.expect('network SSID:', timeout=5)
    print("    Entering network SSID...")
    child.sendline(network)
    child.expect("[Y or N]", timeout=5)
    child.sendline("Y")
    child.expect("Select the type of security[0 to 3]", timeout=5)
    child.sendline("2")
    child.expect("password",timeout=5)
    print("    Entering network password...")
    child.sendline(password)

def login(child, nopass=True):
    """
    Log into slave shell.

    Args:
        child (Pexpect spawn object): Connection to slave.
        nopass (bool): Virgin devices have no root password. This is a flag
            if no password should be used; else use the default Kinetic password.

    Returns:
        bool: True if successfully logged in as root, False otherwise.
    """
    for i in range(10):
        child.send("\010")
    child.send("root\n")
    result = child.expect(["word:", "#", TIMEOUT])
    if result == 1:
        child.sendline("cd ~")  # future commands expect ":~#" for command prompt; make sure we're in home directory
        return True     # already logged in
    if result == 2:
        return False    # timed out
    if nopass:
        child.send("\n")
    else:
        child.sendline("onemm@rga")
    child.send("\n\n")
    result = child.expect([":~#", TIMEOUT])
    return result == 0


if __name__=="__main__":
    """
    Main script. If the initialization procedure gets much more complicated,
    this may need to be refactored as a real state machine.
    """
    print("Initializing GPIOs.")
    initGPIOs()
    for slave in range(N_SLAVES):
        child = None
        try:
            print("Configuring Slave %d." % (slave+1))
            setSlave(slave+1)
            sleep(0.5)             # make sure new GPIO settings have taken effect
            print("    Creating logfile.")
            log = open("init_slave_"+str(slave+1)+".log", 'w')
            print("    Select states:")
            printSelects()
            print("    Flushing serial buffer.")
            flush_uart()
            print("    Creating connection to slave.")
            child = connect()
            child.logfile=log
            print("    Trying to wake slave.")
            # Try RETRIES times to wake slave. Usually a slave device will wake
            # on the first try, occasionally second. 'asleep' is initialized
            asleep = WAKE_STATE_ASLEEP
            for retry in range(RETRIES):
                print "        Try: " + str(retry+1)
                asleep = wakeup(child)
                if asleep != WAKE_STATE_ASLEEP:
                    break
            if asleep == WAKE_STATE_ASLEEP:
                # never woke up; likely not connected.
                print("    Couldn't wake slave %d. Moving on..." % (slave+1))
                log.write("Couldn't wake slave %d. Moving on...\n" % (slave+1))
                child.close()
                log.close()
                continue
            if asleep == WAKE_STATE_AWAKE_LOGGED_IN:
                # device was already logged in
                print("    Already logged in, moving on to WiFi config.")
            else:
                # log in as root
                # if "edison" in command prompt, this device has not been
                # configured. There will be no root password set.
                nopass = "edison" in child.before
                print("    Slave awake, logging in as root.")
                logged_in = False
                for retry in range(RETRIES):
                    logged_in = login(child, nopass)
                    if logged_in:
                        break;
                if logged_in == False:
                    print("    Couldn't log in. Exiting...")
                    log.write("Couldn't log in.\n")
                    child.close()
                    log.close()
                    continue
                print("    We're in! Configuring wifi...")
            configure_wifi(child)
            # Set a long timeout for wifi configuration (60 seconds); it can
            # take some time to connect.
            child.expect(":~#", timeout=60)
            # sleep a couple seconds to ensure connection works
            sleep(2)
            print("    Wifi configured. Downloading files and initializing ota update.")
            start_boot(child)
            child.close()
            log.close()
        except Exception as e:
            log.write("Exited due to exception:\n")
            log.write(str(e))
            if child is not None:
                child.close()
            log.close()
