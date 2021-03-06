#!/usr/bin/env python2.7
#
#   Project Horus 
#   FlDigi -> OziMux Bridge
#
#   Receive sentences from FlDigi, and pass them onto OziMux or OziPlotter.
#   Sentences must be of the form $$CALLSIGN,count,HH:MM:SS,lat,lon,alt,other,fields*CRC16
#
#   TODO:
#   [ ] Accept host/port parameters via a config file.
#   [ ] Better handling of connection timeouts.
#   [ ] Display incoming data 'live'?
#
#   Copyright 2017 Mark Jessop <vk5qi@rfhead.net>
#

import socket
import time
import sys
import Queue
import crcmod
import datetime
import traceback
from threading import Thread
from HorusPackets import *
from PyQt4 import QtGui, QtCore

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
                if self.callback != None:
                    self.callback("ERROR: Could not connect to fldigi. Retrying...")
                time.sleep(10)
                continue

            # OK, now we're connected. Start reading in characters.
            if self.callback != None:
                    self.callback("CONNECTED - WAITING FOR DATA.")

            while self.rx_thread_running:
                try:
                    _char = _s.recv(1)
                except socket.timeout:
                    # No data received? Keep trying...
                    continue
                except:
                    # Something else gone wrong? Try and kill the socket and re-connect.
                    if self.callback != None:
                        self.callback("CONNECTION ERROR!")

                    try:
                        _s.close()
                    except:
                        pass
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


rxqueue = Queue.Queue(32)
data_age = 0.0


# PyQt Window Setup
app = QtGui.QApplication([])

#
# Create and Lay-out window
#
main_widget = QtGui.QWidget()
layout = QtGui.QGridLayout()
main_widget.setLayout(layout)
# Create Widgets


fldigiData = QtGui.QLabel("Not Connected.")
fldigiData.setFont(QtGui.QFont("Courier New", 14, QtGui.QFont.Bold))
fldigiAge = QtGui.QLabel("No Data Yet...")


# Final layout of frames
layout.addWidget(fldigiData)
layout.addWidget(fldigiAge)


mainwin = QtGui.QMainWindow()

# Finalise and show the window
mainwin.setWindowTitle("FlDigi Bridge")
mainwin.setCentralWidget(main_widget)
mainwin.resize(500,50)
mainwin.show()

def data_callback(data):
    global rxqueue
    rxqueue.put(data)

def read_queue():
    global fldigiData, fldigiAge, rxqueue, data_age
    try:
        packet = rxqueue.get_nowait()
        fldigiData.setText(packet)
        data_age = 0.0

    except:
        pass

    # Update 'data age' text.
    data_age += 0.1
    fldigiAge.setText("Packet Data Age: %0.1fs" % data_age)

# Start a timer to attempt to read a UDP packet every 100ms
timer = QtCore.QTimer()
timer.timeout.connect(read_queue)
timer.start(100)


if __name__ == "__main__":

    _fldigi = FldigiBridge(callback=data_callback)

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()
        _fldigi.close()
