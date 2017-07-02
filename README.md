# HorusGroundStation
Ground-station utilities for the LoRa systems used by Project Horus.
Intended to be used to communicate with payloads running: https://github.com/projecthorus/FlexTrack-Horus


## History
* v1.0 - Initial version, no TDMA support. Used on all Project Horus flights from Late 2015 through to November 2016.
* v1.1 - Updated version, in preparation for multiple-payload launches. TDMA support added, numerous packet format and GUI updates.
* v1.2 - Now with low-priority uplink packet support, for relaying of chase car positions. Also merged ChaseTracker (chase car positions to Habitat) into this repository.

## Dependencies
* Python 2.7
  * This should be stock on most modern linux distros.
  * On Windows I recommend the 'Anaconda Python' Distribution, noting that newer versions use PyQt5 by default, and we need PyQt4.
* PyQt4. 
  * Install with: sudo apt-get install python-qt4
  * [TODO] Update all this code to use PyQt5... Any volunteers?
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
 * Note: The tighter timing restrictions needed for the new low priority uplink packets might mean the SPI Bridge interface may not be usable.

## Usage - Client Applications
There are a few example client applications in this repository. Make a copy of defaults.cfg.example as defaults.cfg and edit as appropriate before running any of these.

* HorusGroundStation.py - Horus Cutdown Payload ground-station GUI application, which shows telemetry information and allows commanding of the cutdown payload.
  * This reads some user settings (Callsign, Cutdown Password) from defaults.cfg
* HorusMessenger.py - Basic text-messenger GUI application. Partially deprecated with the addition of 'status' messages to the main HorusGroundStation GUI.
* PacketSniffer.py - Console application which prints a textual representation of all LoRaUDPServer UDP broadcast packets seen on the local network.
* TelemetryUpload.py - Listens for payload telemetry, and uploads to Habitat.
* ChaseTracker.py - Pushes chase car positions from a local GPS (configured in defaults.cfg) to Habitat, and also into the local network via UDP broadcast.
* ChaseTrackerNoGUI.py - Same as above, but with no GUI, suitable for Headless use.
* SummaryGUI.py - A 'Heads Up' GUI with just the basic payload information. Used in my chase car to provide a quick-look display to the driver.



