from pexpect import fdpexpect, TIMEOUT, run, spawn
from time import sleep
import os
import termios
import sys
import re

N_SLAVES = 8
RETRIES = 3

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
        result (int): 1 if child woke up, 0 if not.
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
    send_backspaces()
    print("    Downloading boot script.")
    child.sendline("wget --no-check-certificate http://neil-lakin.com/download/init_firmware.sh")
    child.expect(":~#", timeout=30)
    send_backspaces()   # make sure awake after download.
    print("    Setting to executable...")
    child.sendline("    chmod a+x init_firmware.sh")
    child.expect(":~#")
    print("    Executing...")
    child.sendline("./init_firmware.sh")
    print("    On our way!")
    child.expect("edison-image-edison")

def send_backspaces():
    """
    Send backspaces to keep UART alive.
    """
    for i in range(10):
        child.send("\010")

def flush_uart():
    """
    Flush the serial connection. Flush the terminal file handler, and destroy
    active screen processes. This is extremely important--failing to do this
    results in corrupted reads on the incoming file with increasing bit errors
    on each new connection.
    """
    screens = run("screen -ls").split()
    for line in screens:
        if ".pts" in line:
            session = line.split(".")[0]
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
    """
    for i in range(10):
        child.send("\010")
    child.send("root\n")
    result = child.expect(["word:", ":~#", TIMEOUT])
    if result == 1:
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
    print("Initializing GPIOs.")
    initGPIOs()
    for slave in range(N_SLAVES):
        try:
            print("Configuring Slave %d." % (slave+1))
            setSlave(slave+1)
            sleep(0.5)
            print("    Creating logfile.")
            log = open("init_slave_"+str(slave+1)+".log", 'w')
            print("    Flushing serial buffer.")
            flush_uart()
            # print("Initializing UART1.")
            # out = run('stty -F /dev/ttyMFD1 115200 -parenb -parodd cs8 hupcl -cstopb cread clocal -crtscts -ignbrk -brkint -ignpar -parmrk -inpck -istrip -inlcr -igncr -icrnl -ixon -ixoff -iuclc -ixany -imaxbel iutf8 opost -olcuc -ocrnl onlcr -onocr -onlret -ofill -ofdel nl0 cr0 tab0 bs0 vt0 ff0 -isig -icanon -iexten -echo -echoe -echok -echonl -noflsh -xcase -tostop -echoprt -echoctl -echoke')
            print("    Creating connection to slave.")
            child = connect()
            child.logfile=log
            print("    Trying to wake slave.")
            asleep = 2
            for retry in range(RETRIES):
                print "Try: " + str(retry)
                asleep=wakeup(child)
                if asleep != 2:
                    break
            if asleep == 2:
                print("    Couldn't wake slave %d. Moving on..." % (slave+1))
                log.write("Couldn't wake slave %d. Moving on...\n" % (slave+1))
                child.close()
                log.close()
                continue
            if asleep == 1:
                print("    Already logged in, moving on to WiFi config.")
            else:
                nopass = "edison" in child.before
                print("     Slave awake, logging in as root.")
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
            child.expect(":~#", timeout=60)
            print("    Wifi configured. Downloading files and initializing ota update.")
            start_boot(child)
            sleep(400)
            print(run("ls -al /update"))
            # print child.before
            child.close()
            log.close()
        except Exception as e:
            log.write("Exited due to exception:\n")
            log.write(str(e))
            child.close()
            log.close()
