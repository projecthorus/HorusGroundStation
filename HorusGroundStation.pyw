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
import socket,json,sys,Queue

udp_broadcast_port = HORUS_UDP_PORT
udp_listener_running = False

# RX Message queue to avoid threading issues.
rxqueue = Queue.Queue(16)
txed_packets = []

# PyQt Window Setup
app = QtGui.QApplication([])

# Widgets

# PACKET SNIFFER WIDGET
# Displays a running log of all UDP traffic.
packetSnifferFrame = QtGui.QFrame()
packetSnifferFrame.setFixedSize(1000,150)
packetSnifferFrame.setFrameStyle(QtGui.QFrame.Box)
packetSnifferTitle = QtGui.QLabel("<b><u>Packet Sniffer</u></b>")
console = QtGui.QPlainTextEdit()
console.setReadOnly(True)
packetSnifferLayout = QtGui.QGridLayout()
packetSnifferLayout.addWidget(packetSnifferTitle)
packetSnifferLayout.addWidget(console)
packetSnifferFrame.setLayout(packetSnifferLayout)

# LAST PACKET DATA WIDGET
# Displays RSSI and SNR of the last Received Packet.
lastPacketFrame = QtGui.QFrame()
lastPacketFrame.setFixedSize(220,200)
lastPacketFrame.setFrameStyle(QtGui.QFrame.Box)
lastPacketFrame.setLineWidth(2)
lastPacketTitle = QtGui.QLabel("<b><u>Last Packet</u></b>")
lastPacketTimeLabel = QtGui.QLabel("<b>Timestamp</b>")
lastPacketTimeValue = QtGui.QLabel("No Packet Yet")
lastPacketTypeLabel = QtGui.QLabel("<b>Type:</b>")
lastPacketTypeValue = QtGui.QLabel("None")
lastPacketRSSILabel = QtGui.QLabel("<b>RSSI:</b>")
lastPacketRSSIValue = QtGui.QLabel("-000 dBm")
lastPacketSNRLabel = QtGui.QLabel("<b>SNR:</b>")
lastPacketSNRValue = QtGui.QLabel("00.00 dB")

lastPacketLayout = QtGui.QGridLayout()
lastPacketLayout.addWidget(lastPacketTitle,0,0,1,2)
lastPacketLayout.addWidget(lastPacketTimeLabel,1,0,1,2)
lastPacketLayout.addWidget(lastPacketTimeValue,2,0,1,2)
lastPacketLayout.addWidget(lastPacketRSSILabel,3,0,1,1)
lastPacketLayout.addWidget(lastPacketRSSIValue,3,1,1,1)
lastPacketLayout.addWidget(lastPacketSNRLabel,4,0,1,1)
lastPacketLayout.addWidget(lastPacketSNRValue,4,1,1,1)
lastPacketLayout.addWidget(lastPacketTypeLabel,5,0,1,1)
lastPacketLayout.addWidget(lastPacketTypeValue,5,1,1,1)
lastPacketFrame.setLayout(lastPacketLayout)

# PAYLOAD STATUS WIDGET
# Displays Payload Stats.
payloadStatusFrame = QtGui.QFrame()
payloadStatusFrame.setFixedSize(200,200)
payloadStatusFrame.setFrameStyle(QtGui.QFrame.Box)
payloadStatusFrame.setLineWidth(1)
payloadStatusTitle = QtGui.QLabel("<b><u>Position</u></b>")

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



# Create and Lay-out window
win = QtGui.QWidget()
win.resize(1000,400)
win.show()
win.setWindowTitle("Horus Ground Station")
layout = QtGui.QGridLayout()
win.setLayout(layout)
# Add Widgets
layout.addWidget(lastPacketFrame,0,0,1,1)
layout.addWidget(payloadStatusFrame,0,1,1,1)
layout.addWidget(packetSnifferFrame,1,0,1,3)


#
#	UDP Packet Processing Functions
#	This is where the real work happens!
#


def processPacket(packet):
	# Immediately update the last packet data.
	lastPacketRSSIValue.setText("%d dBm" % packet['rssi'])
	lastPacketSNRValue.setText("%.1f dB" % packet['snr'])
	lastPacketTimeValue.setText(packet['timestamp'])
	
	# Now delve into the payload.
	payload = packet['payload']
	payload_type = decode_payload_type(payload)

	if payload_type == HORUS_PACKET_TYPES.PAYLOAD_TELEMETRY:
		telemetry = decode_horus_payload_telemetry(payload)
		lastPacketTypeValue.setText("Telemetry")
		# Now populate the multitude of labels...
		payloadStatusPacketCountValue.setText("%d" % telemetry['counter'])
		payloadStatusPacketTimeValue.setText(telemetry['time'])
		payloadStatusPacketLatitudeValue.setText("%.5f" % telemetry['latitude'])
		payloadStatusPacketLongitudeValue.setText("%.5f" % telemetry['longitude'])
		payloadStatusPacketAltitudeValue.setText("%d m" % telemetry['altitude'])
		payloadStatusPacketSpeedValue.setText("%d kph" % int(telemetry['speed']))
		payloadStatusPacketSatsValue.setText("%d" % telemetry['sats'])


def process_udp(udp_packet):
	try:
		packet_dict = json.loads(udp_packet)
		
		new_data = udp_packet_to_string(packet_dict)
		console.appendPlainText(new_data)

		if packet_dict['type'] == 'RXPKT':
			processPacket(packet_dict)

	except:
		pass

def udp_rx_thread():
	global udp_listener_running
	s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
	s.settimeout(1)
	s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	s.bind(('',HORUS_UDP_PORT))
	print("Started UDP Listener Thread.")
	udp_listener_running = True
	while udp_listener_running:
		try:
			m = s.recvfrom(1024)
		except socket.timeout:
			m = None
		
		if m != None:
			rxqueue.put_nowait(m[0])
	
	print("Closing UDP Listener")
	s.close()

t = Thread(target=udp_rx_thread)
t.start()

def read_queue():
	try:
		packet = rxqueue.get_nowait()
		process_udp(packet)
	except:
		pass

# Start a timer to attempt to read the remote station status every 5 seconds.
timer = QtCore.QTimer()
timer.timeout.connect(read_queue)
timer.start(100)

## Start Qt event loop unless running in interactive mode or using pyside.
if __name__ == '__main__':
	if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
		QtGui.QApplication.instance().exec_()
		udp_listener_running = False
