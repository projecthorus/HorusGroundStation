#!/usr/bin/env python2.7
#
#   Project Horus 
#   OziPlotter Input Multiplexer
#   Allow switching between multiple data sources for OziPlotter
#   Also provide a unified source of 'Payload Summary' packets.
#   Copyright 2017 Mark Jessop <vk5qi@rfhead.net>
#

import socket
import time
import crcmod
import datetime
import traceback
from threading import Thread
from HorusPackets import *

FLDIGI_PORT = 7322
FLDIGI_HOST = '127.0.0.1'

class FldigiBridge(object):
    """
    Attept to read UKHAS standard telemetry sentences from a local FlDigi instance, 
    and forward them on to either OziPlotter, or OziMux.
    """

    # Receive thread variables and buffers.
    rx_thread_running = True
    MAX_BUFFER_LEN = 256
    input_buffer = ""


    def __init__(self,
                output_hostname = '127.0.0.1',
                output_port = 55683,
                fldigi_host = FLDIGI_HOST,
                fldigi_port = FLDIGI_PORT,
                callback = None,
                ):
    
        self.output_hostname = output_hostname
        self.output_port = output_port
        self.fldigi_host = (fldigi_host, fldigi_port)
        self.callback = callback # Callback should accept a string, which is a valid sentence.

        # Start receive thread.
        self.rx_thread_running = True
        self.t = Thread(target=self.rx_thread)
        self.t.start()

    def close(self):
        self.rx_thread_running = False

    def rx_thread(self):
        """
        Attempt to connect to fldigi and receive bytes.
        """
        while self.rx_thread_running:
            # Try and connect to fldigi. Keep looping until we have connected.
            try:
                _s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                _s.settimeout(1)
                _s.connect(self.fldigi_host)
            except socket.error as e:
                print("ERROR: Could not connect to fldigi - %s" % str(e))
                time.sleep(10)
                continue

            # OK, now we're connected. Start reading in characters.
            while self.rx_thread_running:
                try:
                    # Read a character.
                    try:
                        _char = _s.recv(1)
                    except socket.timeout:
                        traceback.print_exc()
                        continue
                    except:
                        traceback.print_exc()
                        break

                    # Append to input buffer.
                    self.input_buffer += _char
                    # Roll buffer if we've exceeded the max length.
                    if len(self.input_buffer) > self.MAX_BUFFER_LEN:
                        self.input_buffer = self.input_buffer[1:]

                    # If we have received a newline, attempt to process the current buffer of data.
                    if _char == '\n':
                        self.process_data(self.input_buffer)
                        # Clear the buffer and continue.
                        self.input_buffer = ""
                    else:
                        continue
                except:
                    traceback.print_exc()
                    try:
                        _s.close()
                        break
                    except:
                        break

        _s.close()

    def crc16_ccitt(self,data):
        """
        Calculate the CRC16 CCITT checksum of *data*.
        
        (CRC16 CCITT: start 0xFFFF, poly 0x1021)
        """
        crc16 = crcmod.predefined.mkCrcFun('crc-ccitt-false')
        return hex(crc16(data))[2:].upper().zfill(4)


    def process_data(self, data):
        """
        Attempt to process a line of data, and extract time, lat, lon and alt
        """
        try:
            # Try and proceed through the following. If anything fails, we have a corrupt sentence.
            # Strip out any leading/trailing whitespace.
            data = data.strip()

            # First, try and find the start of the sentence, which always starts with '$$''
            _sentence = data.split('$$')[-1]
            # Hack to handle odd numbers of $$'s at the start of a sentence
            if _sentence[0] == '$':
                _sentence = _sentence[1:]
            # Now try and split out the telemetry from the CRC16.
            _telem = _sentence.split('*')[0]
            _crc = _sentence.split('*')[1]

            # Now check if the CRC matches.
            _calc_crc = self.crc16_ccitt(_telem)

            if _calc_crc != _crc:
                return

            # We now have a valid sentence! Extract fields..
            _fields = _telem.split(',')

            _telem_dict = {}
            _telem_dict['time'] = _fields[2]
            _telem_dict['latitude'] = float(_fields[3])
            _telem_dict['longitude'] = float(_fields[4])
            _telem_dict['altitude'] = int(_fields[5])
            # The rest we don't care about.


            # Perform some sanity checks on the data.

            # Attempt to parse the time string. This will throw an error if any values are invalid.
            _time_dt = datetime.strptime(_telem_dict['time'], "%H:%M:%S")

            # Check if the lat/long is 0.0,0.0 - no point passing this along.
            if _telem_dict['latitude'] == 0.0 or _telem_dict['longitude'] == 0.0:
                return

            # Place a limit on the altitude field. We generally store altitude on the payload as a uint16, so it shouldn't fall outside these values.
            if _telem_dict['altitude'] > 65535 or _telem_dict['altitude'] < 0:
                return

            # We now have valid data!

            # If we have been given a callback, send the valid string to it.
            if self.callback !=  None:
                try:
                    self.callback(_sentence)
                except:
                    pass

            # Send the telemetry information onto OziMux/OziPlotter.
            oziplotter_upload_basic_telemetry(_telem_dict, hostname=self.output_hostname, udp_port = self.output_port)

        except:
            return




if __name__ == "__main__":
    def callback(data):
        print(data)

    _fldigi = FldigiBridge(callback=callback)

    # Run until we get Ctrl+C'd
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        _fldigi.close()
