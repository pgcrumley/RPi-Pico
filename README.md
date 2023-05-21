# boot.py Configuration Program for Raspberry Pi Pico & Pico W

When [MicroPython](https://micropython.org/) starts on Pico and Pico W, it
first runs `boot.py`.  This allows the device to be configured before
`main.py` is run.

The `boot.py` program provided here takes a number of actions to 
setup the Pico or Pico W for you.  The actions can be controlled by
settings in an optional `boot.json` file.

The `boot.py` program is most useful on Pico W cards to use 
DHCP to obtain network configuration and then set the time from a 
network time server.

After the network connection is in place, the program can set 
the hostname.  The `#` character in the hostname will be
replaced with the last octet of the IP address in the name.

The program will print details about the system after the above setup is 
performed.

If the `boot.json` file has a `"freq"` entry, `boot.py` will
try to set the frequency of the system clock.  This is done last so 
that other items are complete and messages displayed as it is possible
to "hang" the system with some frequency settings.

Finally, the program cleans up python variables before exiting.

Actions on both Pico & Pico W include:

* optionally delay program start_delay_seconds to allow time to connect a console
* show more details or what is being done if "debug" is set to true
* set the system clock frequency if specified with the "freq" parameter
  * some values have been found to be unusable or dangerous to the hardware

When the code is run on a Pico W, the following `boot.json` fields are used:

* "ssid" provides the SSID for the local WiFi network
* "key" provides the key to connect to a secure WiFi network
* "hostname" provides a hostname.
  * The `#` character is replaced by the last octet of the IP address
* the real time clock (RTC) is set using time from a network time server
  * This is disabled if `"rtc_set"` is `False` in `boot.json`
  * The minutes of difference between local time and UTC can be configured using `"utc_time_offset"`

## Pico vs Pico W

While more functions are available on a Pico W card, the `boot.py` program
will run on both Pico and Pico W cards.

The Pico W image can be installed on a regular Pico card.  This allows the
name of the host image to be set and the code will display various system 
parameters.  When the Pico W image is installed on a regular Pico card, the code will determine
the card type and not try to connect to the network or set the real time clock. 

When the regular Pico image is installed on a Pico W card, it is difficult
to reliably determine that the card is a Pico W rather than Pico card.  In this case, 
the code will not be able to take advantage of the Pico W capabilities and treat
the card as a regular Pico device.

## boot.json file

The following fields can be specified in the `boot.json` file:

* `"ssid"`: "\<str: the SSID of your WiFi network>"
* `"key"`: "\<str: the password or key for your WiFi network>"
* `"hostname"`: "\<str: your hostname with # replaced by last octet of IPv4 address>"
* `"start_delay_seconds"` : \<int: 0 is the default time in seconds to pause>
* `"freq"`: \<int: 125000000 is the default>
* `"utc_time_offset"`: \<int: minutes of offset to UTC time>
* `"rtc_set"`: \<true|false: default is true to set RTC clock>
* `"debug"`: \<true|false: false is the default.  true will override `silent`>
* `"silent"`: \<true|false: false is the default.  true will avoid messages>
* `"flash_led"` : \<true|false: false is the default to not flash the LED as tasks progress> 

  
### Example boot.py files

#### Simple WiFi connection

This connects to a local wifi network and sets the hostname to `pico-N` where `N` is the last
octet of the network address.

If your network address is 192.168.1.23, the hostname will be `pico-23`.

```
{
 "ssid": "home",
 "key": "secret",
 "hostname":"pico-#"
}
```

#### Set time to local timezone

In addition to connecting to the network, this adjusts the timezone to US Eastern Standard time.

```
{
 "ssid": "home",
 "key": "secret",
 "hostname":"pico-#",
  "utc_time_offset": -300
}
```

#### Debugging

This enables debug messages.
The boot.py program will pause 20 seconds to give you time to start a console program.
```
{
 "ssid": "home",
 "key": "secret",
 "hostname":"pico-#",
 "utc_time_offset": -300,
 "debug": true,
 "start_delay_seconds": 20
}
```

## Examples

Two files are provided in the `examples` directory.

### boot.json

You can edit this to include details for your WiFi network, preferred hostname, and time zone.

### main.py

This is a simple program that demonstrates the settings made in the `boot.py` program
persist to the `main.py` program that runs after `boot.py` exits.

## DEBUG file

If a file named `DEBUG` is present in the root filesystem, `/`, the `boot.py` program
will turn on debugging.

## Version History

| Version  | Date | Description |
| -------- | ---- | ----------- |
| 1.0 | 2023-04-24 | Initial version |
| 2.0 | 2023-05-21 | Version for general use (# in hostname, print more info, ...)  Tested on MicroPython v1.20.0 |

## Backlog

* Try to get hostname from DHCP
* Provide ability to set hostname from a map of unique_ids in boot.json
* Provide timeout on network connection
* Send results to file in / to debug when console is not available
