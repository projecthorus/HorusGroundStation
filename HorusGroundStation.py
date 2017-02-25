#!/usr/bin/env python2.7
#
#   Project Horus 
#   LoRa Ground Station Main GUI
#   Copyright 2015 Mark Jessop <vk5qi@rfhead.net>
#

from HorusPackets import *
from threading import Thread
from PyQt4 import QtGui, QtCore
from datetime import datetime
import socket,json,sys,Queue,random,os,math,traceback
import ConfigParser

udp_broadcast_port = HORUS_UDP_PORT
udp_listener_running = False

foxtrot_log = "foxtrot.log"
groundstation_log = "groundstation.log"

# RX Message queue to avoid threading issues.
RX_QUEUE_SIZE = 32
rxqueue = Queue.Queue(RX_QUEUE_SIZE)
txed_packets = []

# PyQt Window Setup
app = QtGui.QApplication([])

timer_update_rate = 0.1 # Seconds
last_packet_timer = 0

current_payload = 0

# Variables for Ground Speed Calculation
lastlat = -34.0
lastlon = 138.0
lasttime = 0.0

# Widgets

# PACKET SNIFFER WIDGET
# Displays a running log of all UDP traffic.
packetSnifferFrame = QtGui.QFrame()
packetSnifferFrame.setFixedSize(800,190)
packetSnifferFrame.setFrameStyle(QtGui.QFrame.Box)
console = QtGui.QPlainTextEdit()
console.setReadOnly(True)
consoleInhibitStatus = QtGui.QCheckBox("Inhibit Status Messages")
consoleInhibitStatus.setChecked(False)
packetSnifferLayout = QtGui.QGridLayout()
packetSnifferLayout.addWidget(consoleInhibitStatus,0,0)
packetSnifferLayout.addWidget(console,1,0)
packetSnifferFrame.setLayout(packetSnifferLayout)

# PAYLOAD SELECTION WIDGET
payloadSelectionFrame = QtGui.QFrame()
payloadSelectionFrame.setFixedSize(150,220)
payloadSelectionFrame.setFrameStyle(QtGui.QFrame.Box)
payloadSelectionFrame.setLineWidth(2)
payloadSelectionTitle = QtGui.QLabel("<b><u>Payload ID</u></b>")
payloadSelectionLabel = QtGui.QLabel("<b>Current:</b>")
payloadSelectionValue = QtGui.QLabel("%d" % current_payload)
payloadSelectionListLabel = QtGui.QLabel("<b>Heard Payloads:</b>")
payloadSelectionList = QtGui.QListWidget()
myCallsignLabel = QtGui.QLabel("<b><u>My Callsign</u></b>")
myCallsignValue = QtGui.QLineEdit("N0CALL")
myCallsignValue.setMaxLength(9)

payloadSelectionLayout = QtGui.QGridLayout()
payloadSelectionLayout.addWidget(payloadSelectionTitle,0,0,1,2)
payloadSelectionLayout.addWidget(payloadSelectionLabel,1,0,1,1)
payloadSelectionLayout.addWidget(payloadSelectionValue,1,1,1,1)
payloadSelectionLayout.addWidget(payloadSelectionListLabel,2,0,1,2)
payloadSelectionLayout.addWidget(payloadSelectionList,3,0,1,2)
payloadSelectionLayout.addWidget(myCallsignLabel,4,0,1,2)
payloadSelectionLayout.addWidget(myCallsignValue,5,0,1,2)
payloadSelectionFrame.setLayout(payloadSelectionLayout)

def newSelectedPayload(curr, prev):
    global current_payload
    current_payload = int(curr.text())
    payloadSelectionValue.setText("%d" % current_payload)
    console.appendPlainText("PAYLOAD SELECTION SET TO #%d" % current_payload)

payloadSelectionList.currentItemChanged.connect(newSelectedPayload)

# LAST PACKET DATA WIDGET
# Displays RSSI and SNR of the last Received Packet.
lastPacketFrame = QtGui.QFrame()
lastPacketFrame.setFixedSize(220,220)
lastPacketFrame.setFrameStyle(QtGui.QFrame.Box)
lastPacketFrame.setLineWidth(2)
lastPacketTitle = QtGui.QLabel("<b><u>Last Packet</u></b>")
lastPacketTimeLabel = QtGui.QLabel("<b>Timestamp</b>")
lastPacketCounterValue = QtGui.QLabel("%.1f seconds ago." % last_packet_timer)
lastPacketTimeValue = QtGui.QLabel("No Packet Yet")
lastPacketTypeLabel = QtGui.QLabel("<b>Type:</b>")
lastPacketTypeValue = QtGui.QLabel("None")
lastPacketIDLabel = QtGui.QLabel("<b>Source/Dest:</b>")
lastPacketIDValue = QtGui.QLabel("-")
lastPacketRSSILabel = QtGui.QLabel("<b>RSSI:</b>")
lastPacketRSSIValue = QtGui.QLabel("-000 dBm")
lastPacketSNRLabel = QtGui.QLabel("<b>SNR:</b>")
lastPacketSNRValue = QtGui.QLabel("00.00 dB")
lastPacketFreqErrorLabel = QtGui.QLabel("<b>Freq Error:</b>")
lastPacketFreqErrorValue = QtGui.QLabel("0000 Hz")

lastPacketLayout = QtGui.QGridLayout()
lastPacketLayout.addWidget(lastPacketTitle,0,0,1,2)
lastPacketLayout.addWidget(lastPacketTimeLabel,1,0,1,2)
lastPacketLayout.addWidget(lastPacketTimeValue,2,0,1,2)
lastPacketLayout.addWidget(lastPacketCounterValue,3,0,1,2)
lastPacketLayout.addWidget(lastPacketRSSILabel,4,0,1,1)
lastPacketLayout.addWidget(lastPacketRSSIValue,4,1,1,1)
lastPacketLayout.addWidget(lastPacketSNRLabel,5,0,1,1)
lastPacketLayout.addWidget(lastPacketSNRValue,5,1,1,1)
lastPacketLayout.addWidget(lastPacketFreqErrorLabel,6,0,1,1)
lastPacketLayout.addWidget(lastPacketFreqErrorValue,6,1,1,1)
lastPacketLayout.addWidget(lastPacketTypeLabel,7,0,1,1)
lastPacketLayout.addWidget(lastPacketTypeValue,7,1,1,1)
lastPacketLayout.addWidget(lastPacketIDLabel,8,0,1,1)
lastPacketLayout.addWidget(lastPacketIDValue,8,1,1,1)
lastPacketFrame.setLayout(lastPacketLayout)

# PAYLOAD STATUS WIDGET
# Displays Payload Stats.
payloadStatusFrame = QtGui.QFrame()
payloadStatusFrame.setFixedSize(180,220)
payloadStatusFrame.setFrameStyle(QtGui.QFrame.Box)
payloadStatusFrame.setLineWidth(1)
payloadStatusTitle = QtGui.QLabel("<b><u>Payload Position</u></b>")

payloadStatusPacketCount = QtGui.QLabel("<b>Count:</b>")
payloadStatusPacketCountValue = QtGui.QLabel("0")
payloadStatusPacketTime = QtGui.QLabel("<b>Time:</b>")
payloadStatusPacketTimeValue = QtGui.QLabel("00:00:00")
payloadStatusPacketLatitude = QtGui.QLabel("<b>Latitude:</b>")
payloadStatusPacketLatitudeValue = QtGui.QLabel("-00.00000")
payloadStatusPacketLongitude = QtGui.QLabel("<b>Longitude:</b>")
payloadStatusPacketLongitudeValue = QtGui.QLabel("000.00000")
payloadStatusPacketAltitude = QtGui.QLabel("<b>Altitude:</b>")
payloadStatusPacketAltitudeValue = QtGui.QLabel("00000m")
payloadStatusPacketSpeed = QtGui.QLabel("<b>Speed</b>")
payloadStatusPacketSpeedValue = QtGui.QLabel("000kph")
payloadStatusPacketSats = QtGui.QLabel("<b>Satellites:</b>")
payloadStatusPacketSatsValue = QtGui.QLabel("0")

payloadStatusLayout = QtGui.QGridLayout()
payloadStatusLayout.addWidget(payloadStatusTitle,0,0,1,2)
payloadStatusLayout.addWidget(payloadStatusPacketCount,1,0)
payloadStatusLayout.addWidget(payloadStatusPacketCountValue,1,1)
payloadStatusLayout.addWidget(payloadStatusPacketTime,2,0)
payloadStatusLayout.addWidget(payloadStatusPacketTimeValue,2,1)
payloadStatusLayout.addWidget(payloadStatusPacketLatitude,3,0)
payloadStatusLayout.addWidget(payloadStatusPacketLatitudeValue,3,1)
payloadStatusLayout.addWidget(payloadStatusPacketLongitude,4,0)
payloadStatusLayout.addWidget(payloadStatusPacketLongitudeValue,4,1)
payloadStatusLayout.addWidget(payloadStatusPacketAltitude,5,0)
payloadStatusLayout.addWidget(payloadStatusPacketAltitudeValue,5,1)
payloadStatusLayout.addWidget(payloadStatusPacketSpeed,6,0)
payloadStatusLayout.addWidget(payloadStatusPacketSpeedValue,6,1)
payloadStatusLayout.addWidget(payloadStatusPacketSats,7,0)
payloadStatusLayout.addWidget(payloadStatusPacketSatsValue,7,1)

payloadStatusFrame.setLayout(payloadStatusLayout)

# PAYLOAD OTHER VALUES
# More payload stats!
payloadOtherStatusFrame = QtGui.QFrame()
payloadOtherStatusFrame.setFixedSize(180,220)
payloadOtherStatusFrame.setFrameStyle(QtGui.QFrame.Box)
payloadOtherStatusFrame.setLineWidth(1)
payloadOtherStatusTitle = QtGui.QLabel("<b><u>Payload Telemetry</u></b>")

payloadOtherStatusBattLabel = QtGui.QLabel("<b>Batt Voltage:</b/>")
payloadOtherStatusBattValue = QtGui.QLabel("0.00 V")
payloadOtherStatusPyroLabel = QtGui.QLabel("<b>Pyro Voltage:</b>")
payloadOtherStatusPyroValue = QtGui.QLabel("0.00 V")
payloadOtherStatusRxPacketsLabel = QtGui.QLabel("<b>RXed Packets:</b>")
payloadOtherStatusRxPacketsValue = QtGui.QLabel("0")
payloadOtherStatusRSSILabel = QtGui.QLabel("<b>Noise Floor:</b>")
payloadOtherStatusRSSIValue = QtGui.QLabel("-000 dBm")
payloadOtherStatusUplinkLabel = QtGui.QLabel("<b>Uplink Slot:</b>")
payloadOtherStatusUplinkValue = QtGui.QLabel("0/0")

payloadOtherStatusLayout = QtGui.QGridLayout()
payloadOtherStatusLayout.addWidget(payloadOtherStatusTitle,0,0,1,2)
payloadOtherStatusLayout.addWidget(payloadOtherStatusBattLabel,1,0)
payloadOtherStatusLayout.addWidget(payloadOtherStatusBattValue,1,1)
payloadOtherStatusLayout.addWidget(payloadOtherStatusPyroLabel,2,0)
payloadOtherStatusLayout.addWidget(payloadOtherStatusPyroValue,2,1)
payloadOtherStatusLayout.addWidget(payloadOtherStatusRxPacketsLabel,3,0)
payloadOtherStatusLayout.addWidget(payloadOtherStatusRxPacketsValue,3,1)
payloadOtherStatusLayout.addWidget(payloadOtherStatusRSSILabel,4,0)
payloadOtherStatusLayout.addWidget(payloadOtherStatusRSSIValue,4,1)
payloadOtherStatusLayout.addWidget(payloadOtherStatusUplinkLabel,5,0)
payloadOtherStatusLayout.addWidget(payloadOtherStatusUplinkValue,5,1)

payloadOtherStatusFrame.setLayout(payloadOtherStatusLayout)


# PING & CUTDOWN Widget
cutdownFrame = QtGui.QFrame()
cutdownFrame.setFixedSize(400,100)
cutdownFrame.setFrameStyle(QtGui.QFrame.Box)
cutdownFrame.setLineWidth(1)
cutdownFrameTitle = QtGui.QLabel("<b><u>Uplink Command</u></b>")

cutdownCommandLabel = QtGui.QLabel("<b>Command</b>")
cutdownCommandValue = QtGui.QComboBox()
cutdownCommandValue.addItem("Ping")
cutdownCommandValue.addItem("Cutdown")
cutdownCommandValue.addItem("Update Rate")
cutdownCommandValue.addItem("Set Payload ID")
cutdownCommandValue.addItem("Set Num Payloads")
cutdownCommandValue.addItem("Reset Uplink Slots")
cutdownParameterLabel = QtGui.QLabel("<b>Value</b>")
cutdownParameterValue = QtGui.QLineEdit("4")
cutdownParameterPasswordLabel = QtGui.QLabel("<b>Password</b>")
cutdownParameterPassword = QtGui.QLineEdit("abc")
cutdownParameterPassword.setMaxLength(3)
cutdownButton = QtGui.QPushButton("Send")

cutdownLayout = QtGui.QGridLayout()
cutdownLayout.addWidget(cutdownFrameTitle,0,0,1,2)
cutdownLayout.addWidget(cutdownCommandLabel,1,0)
cutdownLayout.addWidget(cutdownCommandValue,2,0)
cutdownLayout.addWidget(cutdownParameterLabel,1,1)
cutdownLayout.addWidget(cutdownParameterValue,2,1)
cutdownLayout.addWidget(cutdownParameterPasswordLabel,1,2)
cutdownLayout.addWidget(cutdownParameterPassword,2,2)
cutdownLayout.addWidget(cutdownButton,2,3)

cutdownFrame.setLayout(cutdownLayout)

# Helper functions for the cutdown widget.

def cutdownCommandChanged(text):
    if text == "Ping":
        uplink_value = random.randrange(0,255)
        cutdownParameterValue.setText("%d"%uplink_value)
    elif text == "Cutdown":
        uplink_value = 4
        cutdownParameterValue.setText("%d"%uplink_value)
    elif text == "Update Rate":
        cutdownParameterValue.setText("10")
    elif text == "Set Payload ID":
        cutdownParameterValue.setText("%d"%(current_payload+1))
    elif text == "Set Num Payloads":
        cutdownParameterValue.setText("%d"%(current_payload+1))
    elif text == "Reset Uplink Slots":
        uplink_value = random.randrange(0,255)
        cutdownParameterValue.setText("%d"%uplink_value)
    else:
        pass

cutdownCommandValue.activated[str].connect(cutdownCommandChanged)

def cutdownButtonPressed():
    global current_payload
    cutdown_password = str(cutdownParameterPassword.text())
    uplink_value = int(str(cutdownParameterValue.text()))
    if str(cutdownCommandValue.currentText()) == "Ping":
        ping_packet = create_param_change_packet(param = HORUS_PAYLOAD_PARAMS.PING, value = uplink_value, passcode = cutdown_password, destination = current_payload)
        tx_packet(ping_packet, destination = current_payload)
    elif str(cutdownCommandValue.currentText()) == "Cutdown":
        msgBox = QtGui.QMessageBox()
        msgBox.setText("Are you sure you want to cutdown payload ID #%d?" % current_payload)
        msgBox.setInformativeText("Really really really sure?")
        msgBox.setStandardButtons(QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
        msgBox.setDefaultButton(QtGui.QMessageBox.No)
        reply = msgBox.exec_()
        if reply == QtGui.QMessageBox.No:
            return
        else:
            # Actually Cutdown!
            cutdown_packet = create_cutdown_packet(time=uplink_value,passcode = cutdown_password, destination = current_payload)
            tx_packet(cutdown_packet, destination = current_payload)
    elif str(cutdownCommandValue.currentText()) == "Update Rate":
        param_packet = create_param_change_packet(param = HORUS_PAYLOAD_PARAMS.LISTEN_TIME, value = uplink_value, passcode = cutdown_password, destination = current_payload)
        tx_packet(param_packet, destination = current_payload)
    elif str(cutdownCommandValue.currentText()) == "Set Payload ID":
        # If we have seen a payload with this ID, prompt the user.
        if uplink_value in getHeardPayloadList():
            msgBox = QtGui.QMessageBox()
            msgBox.setText("Specified Payload ID has been seen recently, are you sure?")
            msgBox.setStandardButtons(QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
            msgBox.setDefaultButton(QtGui.QMessageBox.No)
            reply = msgBox.exec_()
            if reply == QtGui.QMessageBox.No:
                return

        msgBox = QtGui.QMessageBox()
        msgBox.setText("Are you sure you want to change Payload #%d to Payload #%d?" % (current_payload, uplink_value))
        msgBox.setStandardButtons(QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
        msgBox.setDefaultButton(QtGui.QMessageBox.No)
        reply = msgBox.exec_()
        if reply == QtGui.QMessageBox.No:
            return

        param_packet = create_param_change_packet(param = HORUS_PAYLOAD_PARAMS.PAYLOAD_ID, value = uplink_value, passcode = cutdown_password, destination = current_payload)
        tx_packet(param_packet, destination = current_payload)
    elif str(cutdownCommandValue.currentText()) == "Set Num Payloads":

        msgBox = QtGui.QMessageBox()
        msgBox.setText("Are you sure you want set Payload #%d's num_payloads variable to %d?" % (current_payload, uplink_value))
        msgBox.setStandardButtons(QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
        msgBox.setDefaultButton(QtGui.QMessageBox.No)
        reply = msgBox.exec_()
        if reply == QtGui.QMessageBox.No:
            return

        param_packet = create_param_change_packet(param = HORUS_PAYLOAD_PARAMS.NUM_PAYLOADS, value = uplink_value, passcode = cutdown_password, destination = current_payload)
        tx_packet(param_packet, destination = current_payload)
    elif str(cutdownCommandValue.currentText()) == "Reset Uplink Slots":

        msgBox = QtGui.QMessageBox()
        msgBox.setText("Are you sure you want to reset Payload #%d's Uplink Slots?" % (current_payload))
        msgBox.setStandardButtons(QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
        msgBox.setDefaultButton(QtGui.QMessageBox.No)
        reply = msgBox.exec_()
        if reply == QtGui.QMessageBox.No:
            return

        param_packet = create_param_change_packet(param = HORUS_PAYLOAD_PARAMS.RESET_SLOTS, value = uplink_value, passcode = cutdown_password, destination = current_payload)
        tx_packet(param_packet, destination = current_payload)

    else:
        pass
cutdownButton.clicked.connect(cutdownButtonPressed)

# UPLINK RESPONSE WIDGET
cutdownResponseFrame = QtGui.QFrame()
cutdownResponseFrame.setFixedSize(400,100)
cutdownResponseFrame.setFrameStyle(QtGui.QFrame.Box)
cutdownResponseFrame.setLineWidth(1)
cutdownResponseFrameTitle = QtGui.QLabel("<b><u>Uplink Response</u></b>")

cutdownResponseTimeLabel = QtGui.QLabel("<b>Packet Time:</b>")
cutdownResponseTimeValue = QtGui.QLabel("No Ack Yet.")
cutdownResponseRSSILabel = QtGui.QLabel("<b>RSSI</b>")
cutdownResponseRSSIValue = QtGui.QLabel("- dBm")
cutdownResponseSNRLabel = QtGui.QLabel("<b>SNR</b>")
cutdownResponseSNRValue = QtGui.QLabel("- dB")
cutdownResponseTypeLabel = QtGui.QLabel("<b>Type</b>")
cutdownResponseTypeValue = QtGui.QLabel("")
cutdownResponseParamLabel = QtGui.QLabel("<b>Parameter</b>")
cutdownResponseParamValue = QtGui.QLabel("")

cutdownResponseLayout = QtGui.QGridLayout()
cutdownResponseLayout.addWidget(cutdownResponseFrameTitle,0,0,1,2)
cutdownResponseLayout.addWidget(cutdownResponseTimeLabel,1,0,1,1)
cutdownResponseLayout.addWidget(cutdownResponseTimeValue,1,1,1,3)
cutdownResponseLayout.addWidget(cutdownResponseRSSILabel,2,0,1,1)
cutdownResponseLayout.addWidget(cutdownResponseRSSIValue,3,0,1,1)
cutdownResponseLayout.addWidget(cutdownResponseSNRLabel,2,1,1,1)
cutdownResponseLayout.addWidget(cutdownResponseSNRValue,3,1,1,1)
cutdownResponseLayout.addWidget(cutdownResponseTypeLabel,2,2,1,1)
cutdownResponseLayout.addWidget(cutdownResponseTypeValue,3,2,1,1)
cutdownResponseLayout.addWidget(cutdownResponseParamLabel,2,3,1,1)
cutdownResponseLayout.addWidget(cutdownResponseParamValue,3,3,1,1)

cutdownResponseFrame.setLayout(cutdownResponseLayout)

uploadFrame = QtGui.QFrame()
uploadFrame.setFixedSize(200,190)
uploadFrame.setFrameStyle(QtGui.QFrame.Box)
uploadFrame.setLineWidth(1)
uploadFrameTitle = QtGui.QLabel("<b><u>Habitat/APRS Upload</u></b>")

uploadFrameHabitat = QtGui.QCheckBox("Habitat Upload")
uploadFrameHabitat.setChecked(False)
uploadFrameHabitatTitle = QtGui.QLabel("Last Upload: ")
uploadFrameOziPlotter = QtGui.QCheckBox("Push Telem to Ozi")
uploadFrameOziPlotter.setChecked(True)
uploadFrameOziPlotterCars = QtGui.QCheckBox("Push Cars to Ozi")
uploadFrameOziPlotterCars.setChecked(True)
uploadFrameFoxTrot = QtGui.QCheckBox("FoxTrotGPS Update")
uploadFrameFoxTrot.setChecked(True)

uploadFrameLayout = QtGui.QGridLayout()
uploadFrameLayout.addWidget(uploadFrameTitle,0,0,1,1)
uploadFrameLayout.addWidget(uploadFrameHabitat,1,0,1,1)
uploadFrameLayout.addWidget(uploadFrameHabitatTitle,2,0,1,1)
uploadFrameLayout.addWidget(uploadFrameOziPlotter,3,0,1,1)
uploadFrameLayout.addWidget(uploadFrameOziPlotterCars,4,0,1,1)
uploadFrameLayout.addWidget(uploadFrameFoxTrot,5,0,1,1)

uploadFrame.setLayout(uploadFrameLayout)

lowpriFrame = QtGui.QFrame()
lowpriFrame.setFixedSize(200,190)
lowpriFrame.setFrameStyle(QtGui.QFrame.Box)
lowpriFrame.setLineWidth(1)
lowpriFrameTitle = QtGui.QLabel("<b><u>Low-Rate Uplink</u></b>")
lowpriFrameEnabled = QtGui.QCheckBox("Enable Car Telemetry")
lowpriFrameEnabled.setChecked(False)
lowpriFrameSlotLabel = QtGui.QLabel("<b>My Slot:</b>")
lowpriFrameSlotValue = QtGui.QLabel("None")
lowpriRequestButton = QtGui.QPushButton("Request")
lowpriResetButton = QtGui.QPushButton("Reset")
lowpriGPSLabel = QtGui.QLabel("<b>My Position</b>")
lowpriGPSValue = QtGui.QLabel("0.0,0.0 0 kph")
lowpriFrameMessage = QtGui.QLineEdit("QRZ?")
lowpriFrameMessage.setMaxLength(CAR_TELEMETRY_MESSAGE_LENGTH)

lowpriFrameLayout = QtGui.QGridLayout()
lowpriFrameLayout.addWidget(lowpriFrameTitle,0,0,1,2)
lowpriFrameLayout.addWidget(lowpriFrameEnabled,1,0,1,2)
lowpriFrameLayout.addWidget(lowpriFrameSlotLabel,2,0,1,1)
lowpriFrameLayout.addWidget(lowpriFrameSlotValue,2,1,1,1)
lowpriFrameLayout.addWidget(lowpriRequestButton,3,0,1,1)
lowpriFrameLayout.addWidget(lowpriResetButton,3,1,1,1)
lowpriFrameLayout.addWidget(lowpriGPSLabel,4,0,1,1)
lowpriFrameLayout.addWidget(lowpriGPSValue,5,0,1,2)
lowpriFrameLayout.addWidget(lowpriFrameMessage,6,0,1,2)

lowpriFrame.setLayout(lowpriFrameLayout)

# Helper functions for the low priority uplink stuff.

# Update the ground station software with the user defined callsign/payload id, which will
# trigger the groundstation to request a slot.
def request_slot():
    update_low_priority_settings(callsign=str(myCallsignValue.text()), destination=current_payload)

lowpriRequestButton.clicked.connect(request_slot)
lowpriResetButton.clicked.connect(reset_low_priority_slot)


def habitat_upload(telemetry):
    sentence = telemetry_to_sentence(telemetry, payload_id=telemetry['payload_id'])
    timestamp = datetime.utcnow().isoformat()
    (success,error) = habitat_upload_payload_telemetry(telemetry,callsign=str(myCallsignValue.text()))
    if success:
        uploadFrameHabitatTitle.setText("Last Upload: %s" % datetime.utcnow().strftime("%H:%M:%S"))
        console.appendPlainText("%s Habitat Upload: %s" % (timestamp, sentence))
    else:
        uploadFrameHabitatTitle.setText("Last Upload: Failed!")
        console.appendPlainText("%s Habitat Upload: FAIL: " % (timestamp, error))

def foxtrot_update(telemetry):
    # Produce and append a line to the log file.
    append_line = "%.5f, %.5f\n" % (telemetry['latitude'],telemetry['longitude'])
    f_log = open(foxtrot_log, 'a')
    f_log.write(append_line)
    f_log.close()
    # Now notify FoxTrotGPS to update
    f_log_filename = os.path.abspath(foxtrot_log)
    try:
        foxsock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        foxsock.sendto(f_log_filename,("127.0.0.1",21234))
        foxsock.close()
    except Exception as e:
        print("Failed to request FoxTrotGPS Update: " % e)

# Now attempt to read in a config file to preset various parameters.
try:
    config = ConfigParser.ConfigParser()
    config.read('defaults.cfg')
    callsign = config.get('User','callsign')
    myCallsignValue.setText(callsign)
    password = config.get('User','password')
    cutdownParameterPassword.setText(password)
except:
    print("Problems reading configuration file, skipping...")

# Delete FoxTrotGPS log file if it exists.
if os.path.exists(foxtrot_log):
    print("Found Existing GPS Log. Removing.")
    os.remove(foxtrot_log)

# Open Ground Station telemetry log for append
gs_log = open(groundstation_log,'a')

#
# Create and Lay-out window
#
main_widget = QtGui.QWidget()
layout = QtGui.QGridLayout()
main_widget.setLayout(layout)
# Add Widgets
layout.addWidget(payloadSelectionFrame,0,0,2,1)
layout.addWidget(lastPacketFrame,0,1,2,1)
layout.addWidget(payloadStatusFrame,0,2,2,1)
layout.addWidget(payloadOtherStatusFrame,0,3,2,1)

layout.addWidget(cutdownFrame,0,4,1,2)
layout.addWidget(cutdownResponseFrame,1,4,1,2)

layout.addWidget(packetSnifferFrame,2,0,1,4)
layout.addWidget(uploadFrame,2,4,1,1)
layout.addWidget(lowpriFrame,2,5,1,1)

mainwin = QtGui.QMainWindow()

#
# Create Menu Bar
#
# Exit Button
exitAction = QtGui.QAction('&Exit', mainwin)        
exitAction.setShortcut('Ctrl+Q')
exitAction.setStatusTip('Exit application')
exitAction.triggered.connect(QtGui.qApp.quit)

# Change frequency Option
def change_frequency():
    text, ok = QtGui.QInputDialog.getText(main_widget,'Change Operating Freq', 'New Freq (MHz):')

    if ok:
        try:
            new_freq = float(text)
            update_frequency(new_freq)
        except:
            print("Invalid frequency selection.")

frequencyAction = QtGui.QAction('&Frequency Change', mainwin)
frequencyAction.setShortcut('Ctrl+F')
frequencyAction.setStatusTip('Change operating frequency of UDP-LoRa bridge.')
frequencyAction.triggered.connect(change_frequency)

menubar = mainwin.menuBar()
menubar.setNativeMenuBar(False)
fileMenu = menubar.addMenu('&File')
fileMenu.addAction(exitAction)

settingsMenu = menubar.addMenu('&Settings')
settingsMenu.addAction(frequencyAction)


# Finalise and show the window
mainwin.setWindowTitle("Horus Ground Station")
mainwin.setCentralWidget(main_widget)
mainwin.show()

#
#   UDP Packet Processing Functions
#   This is where the real work happens!
#

# Speed Calculation Should probably move this to another file.
def speed_calc(lat,lon,lat2,lon2,timediff):
    R = 6373.0

    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c #Distance in km
    speed = 3600*distance/float(timediff)
    return speed

def getHeardPayloadList():
    global payloadSelectionList
    if payloadSelectionList.__len__() == 0:
        return []
    else:
        payloads = []
        for x in range(payloadSelectionList.__len__()):
            # Note that we have to store items in the list as strings, so convert back to int.
            payloads.append(int(payloadSelectionList.item(x).text()))
        return payloads

def processPacket(packet):
    global last_packet_timer, lastlat, lastlon, lasttime, current_payload
    last_packet_timer = 0.0
    # Immediately update the last packet data.
    try:
        lastPacketRSSIValue.setText("%d dBm" % packet['rssi'])
        lastPacketSNRValue.setText("%.1f dB" % packet['snr'])
        lastPacketTimeValue.setText(packet['timestamp'])
        lastPacketFreqErrorValue.setText("%.1f Hz" % packet['freq_error'])
        lastPacketIDValue.setText("%d" % decode_payload_id(packet['payload']))
    except:
        pass

    crc_ok = packet['pkt_flags']['crc_error'] == 0

    if not crc_ok:
        lastPacketTypeValue.setText("CRC Fail!")
        return
    
    # Now delve into the payload.
    payload = packet['payload']

    payload_id = decode_payload_id(payload)

    # If we haven't heard any payloads yet, add this new payload to the list and set it as the current payload.
    if len(getHeardPayloadList()) == 0:
        payloadSelectionList.addItem(str(payload_id))
        payloadSelectionList.setCurrentRow(0)
        current_payload = payload_id

    if payload_id not in getHeardPayloadList():
        payloadSelectionList.addItem(str(payload_id))

    # Only proceed if the data is from our current payload.
    # The decoded string data will still show up in the packet sniffer window.
    if payload_id != current_payload:
        return

    payload_type = decode_payload_type(payload)

    if payload_type == HORUS_PACKET_TYPES.PAYLOAD_TELEMETRY:
        telemetry = decode_horus_payload_telemetry(payload)
        print(telemetry_to_sentence(telemetry))
        lastPacketTypeValue.setText("Telemetry")
        # Now populate the multitude of labels...
        payloadStatusPacketCountValue.setText("%d" % telemetry['counter'])
        payloadStatusPacketTimeValue.setText(telemetry['time'])
        payloadStatusPacketLatitudeValue.setText("%.5f" % telemetry['latitude'])
        payloadStatusPacketLongitudeValue.setText("%.5f" % telemetry['longitude'])
        payloadStatusPacketAltitudeValue.setText("%d m" % telemetry['altitude'])
        #payloadStatusPacketSpeedValue.setText("%d kph" % int(telemetry['speed']))
        payloadStatusPacketSatsValue.setText("%d" % telemetry['sats'])
        payloadOtherStatusBattValue.setText("%.2f V" % telemetry['batt_voltage'])
        payloadOtherStatusPyroValue.setText("%.2f V" % telemetry['pyro_voltage'])
        payloadOtherStatusRxPacketsValue.setText("%d" % telemetry['rxPktCount'])
        payloadOtherStatusRSSIValue.setText("%d dBm" % telemetry['RSSI'])
        payloadOtherStatusUplinkValue.setText("%d/%d" % (telemetry['current_timeslot'],telemetry['used_timeslots']))

        # Calculate Speed
        calculated_speed = speed_calc(lastlat,lastlon,telemetry['latitude'],telemetry['longitude'],telemetry['time_biseconds']*2 - lasttime)
        payloadStatusPacketSpeedValue.setText("%d kph" % int(calculated_speed))
        lastlat = telemetry['latitude']
        lastlon = telemetry['longitude']
        lasttime = telemetry['time_biseconds']*2

        if uploadFrameHabitat.isChecked():
            habitat_upload(telemetry)

        if uploadFrameOziPlotter.isChecked():
            oziplotter_upload_telemetry(telemetry)

        if uploadFrameFoxTrot.isChecked():
            foxtrot_update(telemetry)

    elif payload_type == HORUS_PACKET_TYPES.TEXT_MESSAGE:
        lastPacketTypeValue.setText("Text Message")

    elif payload_type == HORUS_PACKET_TYPES.COMMAND_ACK:
        lastPacketTypeValue.setText("Command Ack")
        cutdownResponseTimeValue.setText(packet['timestamp'])
        command_ack = decode_command_ack(payload)
        cutdownResponseRSSIValue.setText("%d dBm" % command_ack['rssi'])
        cutdownResponseSNRValue.setText("%.1f dB" % command_ack['snr'])
        cutdownResponseTypeValue.setText(command_ack['command'])
        cutdownResponseParamValue.setText(command_ack['argument'])

    elif payload_type == HORUS_PACKET_TYPES.SLOT_REQUEST:
        lastPacketTypeValue.setText("Slot Request")

    elif payload_type == HORUS_PACKET_TYPES.CAR_TELEMETRY:
        lastPacketTypeValue.setText("Car Telem")



def process_udp(udp_packet):
    try:
        packet_dict = json.loads(udp_packet)
        

        if packet_dict['type'] not in ['GPS','LOWPRIORITY']:
            # Avoid flooding the terminal with Local GPS data
            if (packet_dict['type'] == 'STATUS') and consoleInhibitStatus.isChecked():
                pass
            else:
                new_data = udp_packet_to_string(packet_dict)
                console.appendPlainText(new_data)

        if packet_dict['type'] == 'RXPKT':
            # The LoRa Ground station has received a packet.
            processPacket(packet_dict)

        elif packet_dict['type'] == 'STATUS':
            # A status update from the LoRa Ground Station.
            # Process and display some values.
            if packet_dict['uplink_slot_id'] == -1:
                lowpriFrameSlotValue.setText("None")
            else:
                lowpriFrameSlotValue.setText("%d" % packet_dict['uplink_slot_id'])

        elif packet_dict['type'] == 'GPS':
            # Car position update from ChaseTracker.
            if packet_dict['valid']:
                lowpriGPSValue.setText("%.4f,%.4f %d kph" % (packet_dict['latitude'], packet_dict['longitude'], packet_dict['speed']))
                if lowpriFrameEnabled.isChecked():
                    set_low_priority_payload(create_car_telemetry_packet(
                        destination=current_payload,
                        callsign=str(myCallsignValue.text()),
                        latitude=packet_dict['latitude'],
                        longitude=packet_dict['longitude'],
                        speed=packet_dict['speed'],
                        message=str(lowpriFrameMessage.text())
                    ))
                else:
                    set_low_priority_payload([])


    except Exception as e:
        print(udp_packet)
        print(e)
        traceback.print_exc()

def udp_rx_thread():
    global udp_listener_running
    s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    s.settimeout(1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except:
        pass
    s.bind(('',HORUS_UDP_PORT))
    print("Started UDP Listener Thread.")
    udp_listener_running = True
    while udp_listener_running:
        try:
            m = s.recvfrom(MAX_JSON_LEN)
        except socket.timeout:
            m = None
        
        if m != None:
            # Realistically the only way the rx queue will get full is on OSX,
            # where the app goes into a 'nap' state, and the GUI thread stops.
            if rxqueue.qsize()<(RX_QUEUE_SIZE-1):
                rxqueue.put_nowait(m[0])
            else:
                # Discard packets at this point.
                print("UDP Packet discarded.")
                pass

    
    print("Closing UDP Listener")
    s.close()

t = Thread(target=udp_rx_thread)
t.start()

def read_queue():
    global last_packet_timer
    last_packet_timer += timer_update_rate
    try:
        packet = rxqueue.get_nowait()
        process_udp(packet)
    except:
        pass
    lastPacketCounterValue.setText("%.1f seconds ago." % last_packet_timer)

# Start a timer to attempt to read the remote station status every 5 seconds.
timer = QtCore.QTimer()
timer.timeout.connect(read_queue)
timer.start(int(timer_update_rate*1000))

## Start Qt event loop unless running in interactive mode or using pyside.
if __name__ == '__main__':
    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()
        udp_listener_running = False
