#!/usr/bin/env python2.7
#
#   Project Horus 
#   OziPlotter Input Multiplexer
#   Allow switching between multiple data sources for OziPlotter
#   Also provide a unified source of 'Payload Summary' packets.
#   Copyright 2017 Mark Jessop <vk5qi@rfhead.net>
#
import ConfigParser
import socket
import sys
import time
import traceback
import logging
import Queue
from threading import Thread
from PyQt4 import QtGui, QtCore
from HorusPackets import *

# RX Message queue to avoid threading issues.
rxqueue = Queue.Queue(32)

MAX_INPUTS = 4

class TelemetryListener(object):
    """
    Telemetry listener object. Listen on a supplied UDP port for OziPlotter-compatible telemetry data,
    and if enabled, output telemetry to OziPlotter.

    Incoming sentences are of the form:
    TELEMETRY.HH:MM:SS,latitude,longitude,altitude\n
    WAYPOINT,waypoint_name,latitude,longitude,comment\n
    """

    allowed_sentences = ['TELEMETRY', 'WAYPOINT']

    def __init__(self,
                source_name = "None",
                oziplotter_host = "127.0.0.1",
                oziplotter_port = 8942,
                input_port = "55680",
                output_enabled = False,
                summary_enabled = False,
                pass_waypoints = True,
                callback = None):

        self.source_name = source_name
        self.ozi_host = (oziplotter_host, oziplotter_port)
        self.input_port = input_port
        self.output_enabled = output_enabled
        self.summary_enabled = summary_enabled
        self.pass_waypoints = pass_waypoints
        self.callback = callback

        self.udp_listener_running = True

        self.t = Thread(target=self.udp_rx_thread)
        self.t.start()


    def enable_output(self, enabled):
        """
        Set the output enabled flag.
        """
        if enabled:
            self.output_enabled = True
        else:
            self.output_enabled = False

    def enable_summary(self, enabled):
        """
        Set the output enabled flag.
        """
        if enabled:
            self.summary_enabled = True
        else:
            self.summary_enabled= False


    def attach_callback(self, callback):
        self.callback = callback


    def udp_rx_thread(self):
        """
        Listen for incoming UDP packets, and pass them off to another function to be processed.
        """

        print("INFO: Starting Listener Thread: %s, port %d " % (self.source_name, self.input_port))
        self.s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.s.settimeout(1)
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except:
            pass
        self.s.bind(('',self.input_port))
        
        while self.udp_listener_running:
            try:
                m = self.s.recvfrom(256)
            except socket.timeout:
                m = None
            
            if m != None:
                try:
                    self.handle_packet(m[0])
                except:
                    traceback.print_exc()
                    print("ERROR: Couldn't handle packet correctly.")
                    pass
        
        print("INFO: Closing UDP Listener: %s" % self.source_name)
        self.s.close()


    def close(self):
        """
        Close the UDP listener thread.
        """
        self.udp_listener_running = False


    def send_packet_to_ozi(self, packet):
        """
        Send a string to OziPlotter
        """
        try:
            ozisock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            ozisock.sendto(packet,self.ozi_host)
            ozisock.close()
        except Exception as e:
            print("ERROR: Failed to send to OziPlotter: %s" % e)


    def send_packet_summary(self, packet):
        """
        Attempt to parse the incoming packet into fields and send out a payload summary UDP message
        """

        try:
            _fields = packet.split(',')
            _short_time = _fields[1]
            _lat = float(_fields[2])
            _lon = float(_fields[3])
            _alt = int(_fields[4])

            send_payload_summary(self.source_name, _lat, _lon, _alt, short_time = _short_time)
        except:
            traceback.print_exc()


    def handle_packet(self, packet):
        """
        Check an incoming packet matches a valid type, and then forward it on.
        """

        # Extract header (first field)
        packet_type = packet.split(',')[0]

        if packet_type not in self.allowed_sentences:
            print("ERROR: Got unknown packet: %s" % packet)
            return

        # Send received data to a callback function for display on a GUI.
        if self.callback != None:
            try:
                self.callback(self.source_name, packet)
            except:
                pass

        # Now send on the packet if we are allowed to.
        if packet_type == "TELEMETRY" and self.output_enabled:
            self.send_packet_to_ozi(packet)

        if packet_type == "TELEMETRY" and self.output_enabled and self.summary_enabled:
            self.send_packet_summary(packet)

        # Generally we always want to pass on waypoint data.
        if packet_type == "WAYPOINT" and self.pass_waypoints:
            self.send_packet_to_ozi(packet)


def read_config(filename="ozimux.cfg"):
    """
    Read in the ozimux config file.
    """
    config = ConfigParser.ConfigParser()
    config.read(filename)

    config_dict = {}

    config_dict['oziplotter_host'] = config.get("Global", "oziplotter_host")
    config_dict['oziplotter_port'] = config.getint("Global", "oziplotter_port")

    config_dict['number_of_inputs'] = config.getint("Global", "number_of_inputs")

    config_dict['inputs'] = {}

    for n in range(config_dict['number_of_inputs']):
        input_name = config.get("Input_%d"%n, "input_name")
        input_port = config.getint("Input_%d"%n, "input_port")
        input_enabled = config.getboolean("Input_%d"%n, "enabled")

        config_dict['inputs'][input_name] = {}
        config_dict['inputs'][input_name]['port'] = input_port
        config_dict['inputs'][input_name]['enabled_at_start'] = input_enabled

    return config_dict




# PyQt Window Setup
app = QtGui.QApplication([])

#
# Create and Lay-out window
#
main_widget = QtGui.QWidget()
layout = QtGui.QGridLayout()
main_widget.setLayout(layout)
# Create Widgets

data_font_size = 18

input1Frame = QtGui.QFrame()
input1Frame.setFixedSize(400,90)
input1Frame.setFrameStyle(QtGui.QFrame.Box)
input1Frame.setLineWidth(2)
input1Selected = QtGui.QCheckBox("Selected")
input1Title = QtGui.QLabel("<b><u>Not Active</u></b>")
input1Data = QtGui.QLabel("???.?????, ???.?????, ?????")
input1Data.setFont(QtGui.QFont("Courier New", data_font_size, QtGui.QFont.Bold))
input1DataAge = QtGui.QLabel("No Data Yet...")

input1Layout = QtGui.QGridLayout()
input1Layout.addWidget(input1Selected,0,1,1,1)
input1Layout.addWidget(input1Title,0,0)
input1Layout.addWidget(input1Data,1,0,1,2)
input1Layout.addWidget(input1DataAge,2,0,1,2)
input1Frame.setLayout(input1Layout)


input2Frame = QtGui.QFrame()
input2Frame.setFixedSize(400,90)
input2Frame.setFrameStyle(QtGui.QFrame.Box)
input2Frame.setLineWidth(2)
input2Selected = QtGui.QCheckBox("Selected")
input2Title = QtGui.QLabel("<b><u>Not Active</u></b>")
input2Data = QtGui.QLabel("???.?????, ???.?????, ?????")
input2Data.setFont(QtGui.QFont("Courier New", data_font_size, QtGui.QFont.Bold))
input2DataAge = QtGui.QLabel("No Data Yet...")

input2Layout = QtGui.QGridLayout()
input2Layout.addWidget(input2Selected,0,1,1,1)
input2Layout.addWidget(input2Title,0,0)
input2Layout.addWidget(input2Data,1,0,1,2)
input2Layout.addWidget(input2DataAge,2,0,1,2)
input2Frame.setLayout(input2Layout)

input3Frame = QtGui.QFrame()
input3Frame.setFixedSize(400,90)
input3Frame.setFrameStyle(QtGui.QFrame.Box)
input3Frame.setLineWidth(2)
input3Selected = QtGui.QCheckBox("Selected")
input3Title = QtGui.QLabel("<b><u>Not Active</u></b>")
input3Data = QtGui.QLabel("???.?????, ???.?????, ?????")
input3Data.setFont(QtGui.QFont("Courier New", data_font_size, QtGui.QFont.Bold))
input3DataAge = QtGui.QLabel("No Data Yet...")

input3Layout = QtGui.QGridLayout()
input3Layout.addWidget(input3Selected,0,1,1,1)
input3Layout.addWidget(input3Title,0,0)
input3Layout.addWidget(input3Data,1,0,1,2)
input3Layout.addWidget(input3DataAge,2,0,1,2)
input3Frame.setLayout(input3Layout)

input4Frame = QtGui.QFrame()
input4Frame.setFixedSize(400,90)
input4Frame.setFrameStyle(QtGui.QFrame.Box)
input4Frame.setLineWidth(2)
input4Selected = QtGui.QCheckBox("Selected")
input4Title = QtGui.QLabel("<b><u>Not Active</u></b>")
input4Data = QtGui.QLabel("???.?????, ???.?????, ?????")
input4Data.setFont(QtGui.QFont("Courier New", data_font_size, QtGui.QFont.Bold))
input4DataAge = QtGui.QLabel("No Data Yet...")

input4Layout = QtGui.QGridLayout()
input4Layout.addWidget(input4Selected,0,1,1,1)
input4Layout.addWidget(input4Title,0,0)
input4Layout.addWidget(input4Data,1,0,1,2)
input4Layout.addWidget(input4DataAge,2,0,1,2)
input4Frame.setLayout(input4Layout)

# Exclusive CheckBox group
inputSelector = QtGui.QButtonGroup()
inputSelector.addButton(input1Selected,0)
inputSelector.addButton(input2Selected,1)
inputSelector.addButton(input3Selected,2)
inputSelector.addButton(input4Selected,3)
inputSelector.setExclusive(True)

enableSummaryOutput = QtGui.QCheckBox("Enable Payload Summary Output")
enableSummaryOutput.setChecked(True)

# Indexed access to widgets.
inputTitles = [input1Title, input2Title, input3Title, input4Title]
inputData = [input1Data, input2Data, input3Data, input4Data]
inputDataAge = [input1DataAge, input2DataAge, input3DataAge, input4DataAge]
inputActive = [input1Selected, input2Selected, input3Selected, input4Selected]
inputLastData = [0,0,0,0]

# Final layout of frames
layout.addWidget(input1Frame)
layout.addWidget(input2Frame)
layout.addWidget(input3Frame)
layout.addWidget(input4Frame)
layout.addWidget(enableSummaryOutput)

mainwin = QtGui.QMainWindow()

# Finalise and show the window
mainwin.setWindowTitle("OziPlotter Input Mux")
mainwin.setCentralWidget(main_widget)
mainwin.resize(400,100)
mainwin.show()

def telemetry_callback(input_name, packet):
    """
    Place any new data into the receive queue, for processing
    """
    rxqueue.put((input_name,packet))


# Read in config file.
config = read_config("ozimux.cfg")

# Extract input names into a list, which we will iterate through.
input_list = config['inputs'].keys()
input_list.sort()
if len(input_list) > MAX_INPUTS:
    input_list = input_list[:MAX_INPUTS]

num_inputs = len(input_list)

listener_objects = []

# Create Objects
for n in range(num_inputs):
    _obj = TelemetryListener(source_name = input_list[n],
                            oziplotter_host = config['oziplotter_host'],
                            oziplotter_port = config['oziplotter_port'],
                            input_port = config['inputs'][input_list[n]]['port'],
                            output_enabled = config['inputs'][input_list[n]]['enabled_at_start'],
                            summary_enabled = config['inputs'][input_list[n]]['enabled_at_start'],
                            callback = telemetry_callback)

    listener_objects.append(_obj)

    # Set up GUI Widgets
    inputTitles[n].setText("<b><u>%s</u></b>" % input_list[n])
    if config['inputs'][input_list[n]]['enabled_at_start']:
        inputActive[n].setChecked(True)


# Handle checkbox changes.
def handle_checkbox():
    _checked_id = inputSelector.checkedId()
    for n in range(num_inputs):
        if n == _checked_id:
            listener_objects[n].enable_output(True)
            listener_objects[n].enable_summary(enableSummaryOutput.isChecked())
        else:
            listener_objects[n].enable_output(False)
            listener_objects[n].enable_summary(False)

inputSelector.buttonClicked.connect(handle_checkbox)
enableSummaryOutput.stateChanged.connect(handle_checkbox)


def handle_telemetry(input_name, packet):
    try:
        input_index = input_list.index(input_name)
        packet_fields = packet.split(',')

        if packet_fields[0] != 'TELEMETRY':
            return

        short_time = packet_fields[1]
        latitude = float(packet_fields[2])
        longitude = float(packet_fields[3])
        altitude = int(packet_fields[4])

        data_string = "%.5f, %.5f, %d" % (latitude, longitude, altitude)
        inputData[input_index].setText(data_string)
        inputLastData[input_index] = 0.0
    except:
        # Invalid input name, discard.
        return



def read_queue():
    """ Read a packet from the Queue """
    try:
        (input_name, packet) = rxqueue.get_nowait()
        handle_telemetry(input_name, packet)
    except:
        pass

    # Update 'data age' text.
    for n in range(num_inputs):
        inputLastData[n] += 0.1
        inputDataAge[n].setText("Data Age: %0.1fs" % inputLastData[n])


# Start a timer to attempt to read a UDP packet every 100ms
timer = QtCore.QTimer()
timer.timeout.connect(read_queue)
timer.start(100)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()
        # If we get here, we've closed the window. Close all threads.
        for _obj in listener_objects:
            _obj.close()





    






