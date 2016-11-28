# HorusGroundStation
Ground-station utilities for the LoRa systems used by Project Horus.
Intended to be used to communicate with payloads running: https://github.com/projecthorus/FlexTrack-Horus

## Dependencies
* Python 2.7
  * This should be stock on most modern linux distros.
  * On Windows I recommend the 'Anaconda Python' Distribution.
* PyQt4. 
  * Install with: sudo apt-get install python-qt4
* pySX127x (If running a LoRa<->UDP Server)
  * git clone https://github.com/darksidelemm/pySX127x
  * Copy the SX127x directory into this directory. 
* Additional Python Packages (install with pip)
  * crcmod
  * pyserial (if using the SPIBridge interface)
* If using a Raspberry PI, the SPI kernel extension will need to be enabled with raspi-config.
  * You'll also need the python-spidev package

## Hardware
I'm using the HopeRF RFM98W modules, which seem to just have re-branded Semtech SX1276 chips on them. Interface wise, I've written support for two options:
* PiLoRaGateway Raspberry Pi Shield, from Upu's Hab Supplies: http://ava.upuaut.net/store/index.php?route=product/product&path=71_63&product_id=121 
* LoRa Module soldered to a custom arduino shield, connected to a 3.3V Seeeduino board, running the spibridge firmware (see pySX127x/arduino/spibridge). This communicates via a USB-Serial interface.

## Usage - Server
The ground station software consists of a LoRa to UDP gateway server, which pushes all received packets into the local network via UDP broadcast packets (port 55672), and listens for packets to be transmitted.
Refer to INSTALL.rpi for more information on setting up a headless LoRa<->UDP server.
The server can be started using:
* RPi Shield: sudo python LoRaUDPServer.py --rpishield -d <Device Number>
  * where <Device Number> is either 0 (CE0) or 1 (CE1), depending on which RPi chip enable pin the LoRa module is connected to.
* SPI Bridge: python LoRaUDPServer.py --spibridge -d /dev/ttyUSB0

## Usage - Client Applications
There are a few example client applications in this repository
* HorusGroundStation.py - Horus Cutdown Payload ground-station GUI application, which shows telemetry information and allows commanding of the cutdown payload.
  * This can read some user settings (Callsign, Cutdown Password) from defaults.cfg
* HorusMessenger.py - Basic text-messenger GUI application.
* PacketSniffer.py - Console application which prints a textual representation of all LoRaUDPServer UDP broadcast packets seen on the local network.
* TelemetryUpload.py - Listens for payload telemetry, and uploads to Habitat.


