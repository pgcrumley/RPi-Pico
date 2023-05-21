"""
MIT License

Copyright (c) 2023 Paul G Crumley

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

@author: pgcrumley@gmail.com

Code for Raspberry Pi PicoW that:
-- connects to wifi using ssid & key from /boot.json
-- if "hostname" is present in /boot.json, set the network hostname
-- tries to get UTC from a few well-known NTP servers
-- sets the RTC
-- displays system info

The settings are available for the main.py program or interactive use.

The program reads an optional 'boot.json' file containing:
{
 "ssid": "<your wifi ssid>",
 "key":  "<your wifi password>",
 "hostname": "<your hostname>",
 "utc_time_offset" : <minutes from UTC>
 "set_rtc" : true | false,
 "freq" : <system clock frequency to set with machine.freq()
 "silent" : true | false,
 "flash_led" : true | false,
 "start_delay_seconds" : <seconds to delay>,
 "debug" : true | false
}

Notes on contents of boot.json:
  "set_rtc" defaults to true
  "start_delay" defaults to 0 seconds
  "debug" overrides "silent"
  changing system clock frequency can cause unpredictable behavior
  high system clock frequency settings can damage the chip
  problems have been observed when setting freq on Pico W

Backlog:
-- Try to get hostname from DHCP
-- Provide ability to set hostname from a map of unique_ids in boot.json
-- Provide timeout on network connection
-- Send results to file in / to debug when console is not available

Versions:
1.0    2023-04-24  Initial version
2.0    2023-05-21  Version for general use (# in hostname, print more info, ...
                   Tested on MicroPython v1.20.0
TBD         TBD

Notes on what I have learned about Raspberry Pi Pico and Pico W while 
creating boot.py:
-- The suggestions in
    https://www.raspberrypi.com/documentation/microcontrollers/micropython.html
    and some other areas do not seem to be very robust / reliable (for me, at
    least) which is why I use the technique of trying to use the WiFi in a
    non-disruptive manner to test for a Pico W.
    Other suggestions are appreciated.
-- One can use the Pico W image everywhere -- both Pico and Pico W.
-- Rhe Pico image seems to run fine on the Pico W if one needs more storage
    and does not need the Wifi ;-) 
-- The Pico W image seems to run fine on Pico though the LED is set ON. 
    (I assume this is because the same pin is used to select the WiFi chip so
    the Pico W image turns this on.)
-- I have experienced odd device behavior with freq below 60000000.
-- I don't run with freq above 133000000.
-- Other tools generally leave much clutter in memory (try 'dir()' to see).
    I del() the boot.py variables from the running image.

"""

# these should be available in an image
import io
import json
import machine
import os
import struct
import sys
import time

#
# figure out what we are running on
#
IS_PICO_COMPATIBLE = 'rp2' in dir()
IMAGE_SUPPORTS_PICO = 'Pico' in os.uname()[-1]
IMAGE_SUPPORTS_WIFI = False # may get set to true below

try:
    import network
    import socket
    # some other images might support Wi-Fi but being more safe
    if IMAGE_SUPPORTS_PICO:
        IMAGE_SUPPORTS_WIFI = True
except:
    pass # nothing to do

LOG = sys.stderr

VERSION = '2.0'

# default values for parameter from boot.json
SET_RTC = True
SILENT = False
FLASH_LED = False
DEBUG = False
if 'DEBUG' in os.listdir('/'):
    DEBUG = True

BOOT_JSON_FILENAME = '/boot.json'

DEBUG_CONSOLE_DELAY_SECONDS = 10

DEFAULT_CONNECT_RETRIES = 10
DEFAULT_DHCP_RETRIES = 10

TIME_SERVERS = ['time.nist.gov',
                'pool.ntp.org',
                'time.google.com',
                'time.windows.com' 
                ]
NTP_PORT = 123
DEFAULT_TIMEOUT_IN_SECONDS = 1

# subtract this from NTP time to give year UNIX-based EPOCH
SECONDS_BETWEEN_NTP_AND_UNIX_EPOCHS = 2208988800  

# request packet with version = 4 & mode = client (3)
NTP_REQUEST_PACKET = struct.pack('!12I', 
                                 *[0x23000000, # Leap Indicator (2), Version (3), Mode (3), Stratum (8), Poll (8), Precision (8)
                                   0,    # Root Delay (32)
                                   0,    # Root Dispersion (32)
                                   0,    # Reference ID (32) (can set this to correlate replies)
                                   0, 0, # Reference Timestamp (64)
                                   0, 0, # Origin Timestamp (64)
                                   0, 0, # Receive Timestamp (64)
                                   0, 0  # Transmit Timestamp (64)
                                   ]
                                 )

MAXIMUM_SYSTEM_CLOCK_FREQ = 133000000 # docs say 133 MHz is limit
DEFAULT_SYSTEM_CLOCK_FREQ = 125000000 # 
MINIMUM_SYSTEM_CLOCK_FREQ =  60000000 # seems to be the lower bound -- TODO: sort this out

LED_FLASH_MS = 150
LED_POST_FLASH_MS = 500

LED_START_FLASH_COUNT = 1
LED_WIFI_CONNECT_TRY_COUNT = 2
LED_WIFI_CONNECTED_COUNT = 3
LED_TIME_OBTAINED_COUNT = 4
LED_DONE_COUNT = 5

def flash_led(times=1, delay_ms=LED_POST_FLASH_MS):
    """
    flash the LED times times then delay delay_ms
    """
    lp = machine.Pin("LED")
    for i in range(0,times):
        lp.on()
        time.sleep_ms(LED_FLASH_MS)
        lp.off()
        time.sleep_ms(LED_FLASH_MS)
    time.sleep_ms(LED_POST_FLASH_MS)
    
    
def try_to_get_UTC_in_UNIX_seconds():
    """
    Try to get UTC from a time server in UNIX format.
    """
    if not IMAGE_SUPPORTS_WIFI:
        raise RuntimeError('image does not support network') 

    if DEBUG:
        print(f'entering try_to_get_UTC_in_UNIX_seconds()',
              file=LOG)
        
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #client.bind((server_addr, server_port))
    #client.bind(("0.0.0.0", server_port))
    client.settimeout(DEFAULT_TIMEOUT_IN_SECONDS)
    for server in TIME_SERVERS: 
        try:
            addr = socket.getaddrinfo(server, NTP_PORT)[0][-1]
            client.sendto(NTP_REQUEST_PACKET, addr)
            response, addr = client.recvfrom(1024)
            if DEBUG:
                print(f'from {addr} received "{response}"',
                      file=LOG)
            if response:
                reply = struct.unpack('!12I', response)
                if DEBUG:
                    print('reply:', file=LOG)
                    print(f'  {reply[ 0]:#10x}', file=LOG)
                    print(f'  {reply[ 1]:#10x}', file=LOG)
                    print(f'  {reply[ 2]:#10x}', file=LOG)
                    print(f'  {reply[ 3]:#10x}', file=LOG)
                    print(f'  {reply[ 4]:#10x}', file=LOG)
                    print(f'  {reply[ 5]:#10x}', file=LOG)
                    print(f'  {reply[ 6]:#10x}', file=LOG)
                    print(f'  {reply[ 7]:#10x}', file=LOG)
                    print(f'  {reply[ 8]:#10x}', file=LOG)
                    print(f'  {reply[ 9]:#10x}', file=LOG)
                    print(f'  {reply[10]:#10x}', file=LOG)
                    print(f'  {reply[11]:#10x}', file=LOG)
                    print(' ', file=LOG)
                    
                return reply[10] - SECONDS_BETWEEN_NTP_AND_UNIX_EPOCHS
        except Exception as ex:
            if DEBUG:
                print(f'while trying to receive from NTP server caught "{ex}"',
                      file=LOG)

    raise RuntimeError(f'count not get response from any of {TIME_SERVERS}')
    
def is_a_pico_w():
    '''
    Guess if this is a Pico W based on whether it can scan for WiFi Access
    Points

    Note: if this is the Pico image (no network or socket) this will return
    False even if this is really a Pico W as the Pico image does not have
    support for this operation
    
    Return True if it can scan(), False if it can not.
    '''
    if not IMAGE_SUPPORTS_WIFI:
        return False
    
    result = False # assume not until demonstrated otherwise
        
    w = network.WLAN(network.STA_IF)
    saved_active_status = w.active()
    w.active(True)
    try:
        w.scan()
        result = True
    except:
        result = False
    finally:
        if False == saved_active_status:
            w.active(False)
    
    return result    

def connect_using_DHCP(ssid=None, key=None):
    '''
    try to connect to wifi network with a given ssid and key (password)
    
    will try forever
    '''
    if not IMAGE_SUPPORTS_WIFI:
        raise RuntimeError('image does not support network') 

    if DEBUG:
        print('starting connect_using_DHCP to get IP parameters',
              file=LOG)

    wlan = network.WLAN(network.STA_IF)
    network_ready = False
    while (not network_ready):
        if FLASH_LED:
            flash_led(LED_WIFI_CONNECT_TRY_COUNT)
        wlan.active(True)
        wlan.connect(ssid, key)
    
        for i in range(DEFAULT_CONNECT_RETRIES): 
            if i > 0:  # wait a bit before a retry
                time.sleep(1)
    
            if wlan.isconnected():
                if DEBUG:
                    print(f'connected, wlan.status() is "{wlan.status()}"',
              file=LOG)
            else:
                if DEBUG:
                    print(f'Waiting to connect...  wlan.status() is "{wlan.status()}"',
              file=LOG)
                continue
            if wlan.status() == 3:
                network_ready = True
                break
    
        if not network_ready:
            # tell status before trying again
            wlan.active(False)
            if DEBUG:
                print(f'did not connect after {DEFAULT_CONNECT_RETRIES} tries...',
              file=LOG)
                print(f'trying again as wlan.status() is "{wlan.status()}"',
              file=LOG)
    
    if FLASH_LED:
        flash_led(LED_WIFI_CONNECTED_COUNT)
    if DEBUG:
        print(f'network_ready with wlan.ifconfig = {wlan.ifconfig()}',
              file=LOG)

"""
MAIN
"""
#
# look for a JSON file with details for this system
#
boot_info = {}
start_delay_seconds = 0
try:
    with io.open(BOOT_JSON_FILENAME, 'r') as bjf:
        boot_info = json.load(bjf)
    del(bjf)
    if "flash_led" in boot_info:
        FLASH_LED = boot_info["flash_led"]
    if "set_rtc" in boot_info:
        SET_RTC = boot_info["set_rtp"]
    if "silent" in boot_info:
        SILENT = boot_info["silent"]
    if "start_delay_seconds" in boot_info:
        start_delay_seconds = boot_info["start_delay_seconds"]
    if "debug" in boot_info:
        DEBUG = DEBUG | boot_info["debug"]
        SILENT = False

    if FLASH_LED:
        flash_led(LED_START_FLASH_COUNT)    
    if DEBUG:
        print(f'Found and read "{BOOT_JSON_FILENAME}" file',
              file=LOG)
except Exception as ex:
    print(f'No valid "{BOOT_JSON_FILENAME}" file found',
          file=sys.stderr)
    print(f'cause: "{ex}"',
          file=sys.stderr)

# give some time to start USB console program if connecting to another compute for power / console
time.sleep(start_delay_seconds)

if not SILENT:
    print(' ')
    print('Welcome to boot.py, which can')
    print('    connect to WiFi, set the hostname, get NTP time, and set the RTC.')
    print(f'Version {VERSION}')
    print('Copyright (c) 2023 Paul G Crumley')
    print(' ')

#
# this will be used below
#
rtc = machine.RTC()

#
# if Wi-Fi is supported, try to connect to wifi if ssid & key are given
#
if IMAGE_SUPPORTS_WIFI:
    this_is_a_pico_w = is_a_pico_w() # save for later use
    
    if 'ssid' in boot_info and 'key' in boot_info:
        if this_is_a_pico_w:
            connect_using_DHCP(boot_info['ssid'], boot_info['key'])
            # set hostname if template given in boot.json
            last_octet = 'TBD'
            hn = 'TBD'
            if 'hostname' in boot_info:
                hn = boot_info['hostname']
                if '#' in hn:
                    last_octet = network.WLAN().ifconfig()[0].split('.')[-1]
                    if DEBUG:
                        print(f'last_octect = "{last_octet}"',
                              file=LOG)
                        print(f'hn = "{hn}"',
                              file=LOG)
                    hn = hn.replace('#', last_octet)
                network.hostname(hn)
            del(last_octet, hn)
        else:
            print('ssid and key provided but this is not a Pico W',
                  file=sys.stderr)
    else:
        print('ssid and key are not provided so not able to connect to WiFi')
    
    #
    # try to get UTC from network
    #
    if SET_RTC:
        if network.WLAN().isconnected():
            try:
                utc_time = try_to_get_UTC_in_UNIX_seconds()
                if FLASH_LED:
                    flash_led(LED_TIME_OBTAINED_COUNT)
                if DEBUG:
                    print(f'try_to_get_UTC_in_UNIX_seconds() returned {utc_time}',
                          file=LOG)
                    print(f'setting RTC to "{time.gmtime(utc_time)}"...',
                          file=LOG)
                (year, month, day, hour, minute, second, weekday, yearday) = time.gmtime(utc_time)
                rtc.datetime( (year, month, day, 0, hour, minute, second, 0) ) 
                if DEBUG:
                    print(f'time.gmtime() returns {time.gmtime()}',
                          file=LOG)
                    print('done',
                          file=LOG)
            except Exception as ex:
                print('could not obtain UTC from known servers, RTC not set')
            finally:
                del(utc_time, year, month, day, hour, minute, second, weekday, yearday) 
    
        else:
            print('can not set RTC from NTP as there is no network connection')
  
#
# optionally adjust for local time
#
if "utc_time_offset" in boot_info:
    if DEBUG:
        print('shifting time by "utc_time_offset"',
              file=LOG)
        print(f'time.gmtime() now returns {time.gmtime()}',
              file=LOG)
    time_offset_seconds = boot_info["utc_time_offset"] * 60
    if DEBUG:
        print(f'shifting time by {time_offset_seconds} seconds',
              file=LOG)
    local_time = time.time() + time_offset_seconds
    (year, month, day, hour, minute, second, weekday, yearday) = time.gmtime(local_time)
    rtc.datetime( (year, month, day, 0, hour, minute, second, 0) ) 
    if DEBUG:
        print(f'time.gmtime() returns {time.gmtime()}',
              file=LOG)
        print('done',
              file=LOG)
    del(time_offset_seconds, local_time)
    del(year, month, day, hour, minute, second, weekday, yearday)

  
#
# Display details
#
if not SILENT:
    print(f'Image supports Pico : {IMAGE_SUPPORTS_PICO}')
    print(f'Image supports WiFi : {IMAGE_SUPPORTS_WIFI}')
    print(f'Is Pico compatible :  {IS_PICO_COMPATIBLE}')
    print(f'os release :          "{os.uname()[2]}"')
    print(f'os version :          "{os.uname()[3]}"')
    print(f'os machine :          "{os.uname()[4]}"')
    print(f'machine.unique_id() : {machine.unique_id().hex()}')
    print(f'machine.freq() :      {machine.freq()}')
    if IMAGE_SUPPORTS_WIFI:
        if this_is_a_pico_w:
            print(f'hostname :            "{network.hostname()}"')
            if network.WLAN().isconnected():
                print(f'WiFi IP Address :       {network.WLAN().ifconfig()[0]}')
                print(f'WiFi Netmask :          {network.WLAN().ifconfig()[1]}')
                print(f'WiFi Gateway :          {network.WLAN().ifconfig()[2]}')
                print(f'WiFi Name Server :      {network.WLAN().ifconfig()[3]}')
            else:
                print('System is not connected to WiFi network.')
        else:
            print('WiFi image is running on a regular Pico.  No network details to report.')
    else:
        print('Regular Pico image does not support network functions.')
    print( 'RTC date & time :     {}/{}/{}  {}:{:02}:{:02}'.format(rtc.datetime()[0], 
                                                                   rtc.datetime()[1],
                                                                   rtc.datetime()[2],
                                                                   rtc.datetime()[4],
                                                                   rtc.datetime()[5],
                                                                   rtc.datetime()[6]
                                                                   ))
    print('files in "/":')
    for filename in os.listdir('/'):
        print(f'   "{filename}"')
    del(filename)
    print(' ')

#
# set the system clock last as it can cause troubles
#
if "freq" in boot_info:
    new_freq = boot_info["freq"]
    if not SILENT:
        print(f'Attempting to set system clock frequency to {new_freq}...')
    if new_freq > MAXIMUM_SYSTEM_CLOCK_FREQ:
        print(f'WARNING: freq of {new_freq} is higher than published limit of {MAXIMUM_SYSTEM_CLOCK_FREQ}!!')
    machine.freq(new_freq)
    if not SILENT:
        print(f'Done setting system clock frequency to {new_freq}')
        print(f'machine.freq() :      {machine.freq()}')
    del (new_freq)

#
# cleanup
#
if not DEBUG:
    if IMAGE_SUPPORTS_WIFI:
        del(network, socket, this_is_a_pico_w)
    del(LOG)
    del(DEBUG, VERSION, DEBUG_CONSOLE_DELAY_SECONDS, start_delay_seconds)
    del(BOOT_JSON_FILENAME, boot_info)

    del(DEFAULT_CONNECT_RETRIES, DEFAULT_DHCP_RETRIES, TIME_SERVERS, NTP_PORT, DEFAULT_TIMEOUT_IN_SECONDS)
    del(SECONDS_BETWEEN_NTP_AND_UNIX_EPOCHS, NTP_REQUEST_PACKET)
    del(try_to_get_UTC_in_UNIX_seconds, connect_using_DHCP)
    del(MAXIMUM_SYSTEM_CLOCK_FREQ, DEFAULT_SYSTEM_CLOCK_FREQ, MINIMUM_SYSTEM_CLOCK_FREQ)
    del(IMAGE_SUPPORTS_PICO, IMAGE_SUPPORTS_WIFI, IS_PICO_COMPATIBLE, is_a_pico_w, SET_RTC, rtc)
    del(io, json, os, struct, sys)
    
    import gc
    gc.collect()
    del(gc)

if FLASH_LED:
    flash_led(LED_DONE_COUNT, delay_ms=0)
del(time)
del(LED_FLASH_MS, LED_POST_FLASH_MS, LED_START_FLASH_COUNT, LED_WIFI_CONNECT_TRY_COUNT)
del(LED_WIFI_CONNECTED_COUNT,LED_TIME_OBTAINED_COUNT, LED_DONE_COUNT)
del(flash_led, FLASH_LED)

if not SILENT:
    print('boot.py done')
    print('exiting boot.py')
    print('')
del(SILENT)

# end of boot.py
