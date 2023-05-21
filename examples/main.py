#!/usr/bin/env python3
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

Sample micropython main.py which shows setup from boot.py persists to mail.py.

Versions:
1.0    2023-05-21  Version for general use

"""

VERSION = '1.0'
print(' ')
print('Welcome to main.py which shows settings from boot.py are persistent.')
print(f'Version {VERSION}')
print('Copyright (c) 2023 Paul G Crumley')
print(' ')
del(VERSION)

#
# show that time and network settings persist to main.py
#
import machine
rtc = machine.RTC()
print('RTC date & time :     {}/{}/{}  {}:{:02}:{:02}'.format(rtc.datetime()[0], 
                                                              rtc.datetime()[1],
                                                              rtc.datetime()[2],
                                                              rtc.datetime()[4],
                                                              rtc.datetime()[5],
                                                              rtc.datetime()[6]
                                                              ))
del(rtc)

try:
    import network
    print(f'hostname :            "{network.hostname()}"')
    print(f'WiFi IP Address :       {network.WLAN().ifconfig()[0]}')
    print(f'WiFi Netmask :          {network.WLAN().ifconfig()[1]}')
    print(f'WiFi Gateway :          {network.WLAN().ifconfig()[2]}')
    print(f'WiFi Name Server :      {network.WLAN().ifconfig()[3]}')
    del(network)
except:
    print('Network functions are not available.')

print(' ')
print('exiting main.py')
print(' ')
