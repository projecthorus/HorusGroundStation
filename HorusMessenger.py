#!/usr/bin/env python2.7
#
#   Project Horus 
#   LoRa Text Messenger
#   Copyright 2015 Mark Jessop <vk5qi@rfhead.net>
#

from HorusPackets import *
from threading import Thread
from PyQt4 import QtGui, QtCore
import socket,json,sys,Queue

udp_broadcast_port = HORUS_UDP_PORT
udp_listener_running = False

# RX Message queue to avoid threading issues.
rxqueue = Queue.Queue(16)
txed_packets = []

# PyQt Window Setup
app = QtGui.QApplication([])

# Widgets
console = QtGui.QPlainTextEdit()
console.setReadOnly(True)
callsignBox = QtGui.QLineEdit("N0CALL")
callsignBox.setFixedWidth(100)
callsignBox.setMaxLength(8)
messageBox = QtGui.QLineEdit("")
messageBox.setMaxLength(55)

# Create and Lay-out window
win = QtGui.QWidget()
win.resize(500,200)
win.show()
win.setWindowTitle("Horus Messenger")
layout = QtGui.QGridLayout()
win.setLayout(layout)
# Add Widgets
layout.addWidget(console,0,0,1,4)
layout.addWidget(callsignBox,1,0,1,1)
layout.addWidget(messageBox,1,1,1,3)

# Send a message!
def send_message():
	callsign = str(callsignBox.text())
	message = str(messageBox.text())
	message_packet = create_text_message_packet(callsign,message)
	tx_packet(message_packet)
	messageBox.setText("")

messageBox.returnPressed.connect(send_message)
callsignBox.returnPressed.connect(send_message)


# Method to process UDP packets.
def process_udp(udp_packet):
	try:
		packet_dict = json.loads(udp_packet)

		# TX Confirmation Packet?
		if packet_dict['type'] == 'TXDONE':
			if(packet_dict['payload'][0] == HORUS_PACKET_TYPES.TEXT_MESSAGE):
				(source,message) = read_text_message_packet(packet_dict['payload'])
				line = "< %8s > %s" % (source,message)
				rxqueue.put_nowait(line)
		elif packet_dict['type'] == 'RXPKT':
			if(packet_dict['payload'][0] == HORUS_PACKET_TYPES.TEXT_MESSAGE):
				print packet_dict['payload']
				(source,message) = read_text_message_packet(packet_dict['payload'])
				if source == str(callsignBox.text()) and decode_payload_flags(packet_dict['payload'])['is_repeated']:
					line = "(repeat) < %8s > %s" % (source,message)
				else:
					line = "< %8s > %s" % (source,message)
				rxqueue.put_nowait(line)
			else:
				print("Got other packet type...")
				print packet_dict['payload']
		else:
			pass
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
			if m != None:
				process_udp(m[0])
		except Exception as e:
			print(e)
			print("ERROR: Received Malformed UDP Packet")
	
	print("Closing UDP Listener")
	s.close()

t = Thread(target=udp_rx_thread)
t.start()

def read_queue():
	try:
		line = rxqueue.get_nowait()
		console.appendPlainText(line)
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
