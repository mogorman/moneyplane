#!/bin/bash
#set -euo pipefail

# This script will setup a simple HID keyboard gadget via ConfigFS.
# In order to use it, you must have kernel >= 3.19 and configfs enabled
# when the kernel was compiled (it usually is).

IMAGE_FILE=/data/media/media.img
MOUNT=/data/media/usb_disk
if [ ! -f $IMAGE_FILE ]; then
	exit 0
fi
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
mkdir /sys/kernel/config/usb_gadget/gah                           #  make a new gadget skeleton
cd /sys/kernel/config/usb_gadget/gah                              #  cd to gadget dir
mkdir configs/c.1                                                 #  make the skeleton for a config for this gadget
mkdir functions/mass_storage.0
# partition(lun?) 0 created by default
#echo /data/media/0/realdata > functions/mass_storage.0/lun.0/file
#comma@tici:/data/files/gadget/keyboard-gadget$ sudo bash ./gadget-setup.sh 
#./gadget-setup.sh: line 29: echo: write error: Is a directory
echo $IMAGE_FILE > functions/mass_storage.0/lun.0/file
#echo $PROTOCOL > functions/hid.usb0/protocol                      #  set the HID protocol
#echo $SUBCLASS > functions/hid.usb0/subclass                      #  set the device subclass
#echo $REPORT_LENGTH > functions/hid.usb0/report_length            #  set the byte length of HID reports
#cat $DESCRIPTOR > functions/hid.usb0/report_desc                  #  write the binary blob of the report descriptor to report_desc; see HID class spec
mkdir strings/0x409                                               #  setup standard device attribute strings
mkdir configs/c.1/strings/0x409
echo $IDPRODUCT > idProduct
echo $IDVENDOR > idVendor
echo $SERIAL > strings/0x409/serialnumber
echo $MANUFACTURER > strings/0x409/manufacturer
echo $PRODUCT > strings/0x409/product
echo $CONFIG_NAME > configs/c.1/strings/0x409/configuration
echo $MAX_POWER_MA > configs/c.1/MaxPower
ln -s functions/mass_storage.0 configs/c.1                              #  put the function into the configuration by creating a symlink

# binding
echo "" >UDC
echo $UDC > UDC                                                   #  bind gadget to UDC driver (brings gadget online). This will only
                                                                  #  succeed if there are no gadgets already bound to the driver. Do
                                                                  #  lsmod and if there's anything in there like g_*, you'll need to
                                                                  #  rmmod it before bringing this gadget online. Otherwise you'll get
umount $MOUNT
mount -o loop,rw,uid=1000,gid=1000 $IMAGE_FILE $MOUNT                                                                 #  "device or resource busy."

