# HorusGroundStation
Ground-station utilities for the LoRa systems used by Project Horus.

## Dependencies
* Python 2.7 (Will eventually work with Python 3, but not yet)
* Additional Python Packages (install with pip)
  * crcmod
  * pyserial (if using the SPIBridge interface)
* If using a Raspberry PI, the SPI kernel extension will need to be enabled with raspi-config.

## Hardware
I'm using the HopeRF RFM98W modules, which seem to just have re-branded Semtech SX1276 chips on them. Interface wise, I've written support for two options:
* PiLoRaGateway Raspberry Pi Shield, from Upu's Hab Supplies: http://ava.upuaut.net/store/index.php?route=product/product&path=71_63&product_id=121 
* LoRa Module soldered to a custom arduino shield, connected to a 3.3V Seeeduino board, running the spibridge firmware (see arduino/spibridge). This communicates via a USB-Serial interface.

## Usage - Server
The ground station software consists of a LoRa to UDP gateway server, which pushes all received packets into the local network via UDP broadcast packets (port 55672), and listens for packets to be transmitted.
The server can be started using:
* RPi Shield: sudo python LoRaUDPServer.py --rpishield -d <Device Number>
  * where <Device Number> is either 0 (CE0) or 1 (CE1), depending on which RPi chip enable pin the LoRa module is connected to.
* SPI Bridge: python LoRaUDPServer.py --spibridge -d /dev/ttyUSB0

## Usage - Client Applications
There are a few example client applications in this repository
* HorusGroundStation.pyw - Horus Cutdown Payload ground-station GUI application, which shows telemetry information and allows commanding of the cutdown payload.
* HorusMessenger.py - Basic text-messenger GUI application.
* PacketSniffer.py - Console application which prints a textual representation of all LoRaUDPServer UDP broadcast packets seen on the local network.
* TelemetryUpload.py - Listens for payload telemetry, and uploads to Habitat.


