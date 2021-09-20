#!/bin/bash
#set -euo pipefail

# This script will setup a simple HID keyboard gadget via ConfigFS.
# In order to use it, you must have kernel >= 3.19 and configfs enabled
# when the kernel was compiled (it usually is).

# variables and strings
MANUFACTURER="openpilot community"                                #  manufacturer attribute
SERIAL="ieatass123"                                               #  device serial number
IDPRODUCT="0xa4ac"                                                #  hex product ID, issued by USB Group
IDVENDOR="0x0525"                                                 #  hex vendor ID, assigned by USB Group
PRODUCT="openpilot video storage"                                 #  cleartext product description
CONFIG_NAME="Configuration 1"                                     #  name of this configuration
MAX_POWER_MA=120                                                  #  max power this configuration can consume in mA
PROTOCOL=1                                                        #  1 for keyboard. see usb spec
SUBCLASS=1                                                        #  it seems either 1 or 0 works, dunno why
REPORT_LENGTH=8                                                   #  number of bytes per report
#DESCRIPTOR=/data/files/gadget/keyboard-gadget/kybd-descriptor.bin  #  binary blob of report descriptor, see HID class spec
UDC=a600000.dwc3                                                  #  name of the UDC driver to use (found in /sys/class/udc/)   


# gadget configuration
cd /sys/kernel/config/usb_gadget/gah                              #  cd to gadget dir
# binding
echo "" >UDC
echo $UDC > UDC                                                   #  bind gadget to UDC driver (brings gadget online). This will only
                                                                  #  succeed if there are no gadgets already bound to the driver. Do
                                                                  #  lsmod and if there's anything in there like g_*, you'll need to
                                                                  #  rmmod it before bringing this gadget online. Otherwise you'll get

