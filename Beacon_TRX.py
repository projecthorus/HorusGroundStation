#!/usr/bin/env python2.7
#
#   Project Horus 
#   LoRa Text Messenger
#   Copyright 2015 Mark Jessop <vk5qi@rfhead.net>
#

from HorusPackets import *
from threading import Thread
from datetime import datetime
import socket,json,sys,Queue,argparse,time

udp_broadcast_port = HORUS_UDP_PORT
udp_listener_running = False

parser = argparse.ArgumentParser()
parser.add_argument("callsign", help="Listener Callsign",default="N0CALL")
parser.add_argument("tx_time", help="TX timeslot",default=0)
parser.add_argument("-l","--log_file",default="beaconrx.log",help="Log file for RX Telemetry")
args = parser.parse_args()

mycall = str(args.callsign)
mytime = int(args.tx_time)

def write_log_entry(packet):
	timestamp = datetime.utcnow().isoformat()
	rssi = str(packet['rssi'])
	snr = str(packet['snr'])
	freq_error = str(packet['freq_error'])
	if packet['pkt_flags']['crc_error'] != 0:
		#sentence = "CRC FAIL\n"
		# Don't log packets with failed CRCs.
		return
	else:
		if decode_payload_type(packet['payload']) == HORUS_PACKET_TYPES.TEXT_MESSAGE:
			(source,message) = read_text_message_packet(packet['payload'])
			sentence = "%s %s" % (source, message)
		else:
			return

	log = open(args.log_file,'a')
	log_string = "%s,%s,%s,%s,%s\n" % (timestamp,rssi,snr,freq_error,sentence)
	print(log_string)
	log.write(log_string)
	log.close()


def process_udp(udp_packet):
	try:
		packet = json.loads(udp_packet)
		# Only process received telemetry packets.
		if packet['type'] == "TXDONE":
			print "We just Transmitted!"

		if packet['type'] != "RXPKT":
			return

		write_log_entry(packet)
	except Exception as e:
		print("Invalid packet, or decode failed: %s" % e)

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
			m = s.recvfrom(MAX_JSON_LEN)
		except socket.timeout:
			m = None
		
		if m != None:
			process_udp(m[0])
	
	print("Closing UDP Listener")
	s.close()

t = Thread(target=udp_rx_thread)
t.start()


# Do Transmit stuff here.

def tx_thread():
	while True:
		if datetime.now().second == mytime:
			# Transmit!
			packet = create_text_message_packet(source=mycall,message="BEACON")
			tx_packet(packet)
			time.sleep(10) # Sleep to make sure we dont retransmit.
		else:
			time.sleep(0.5)
			pass

try:
	tx_thread()
except KeyboardInterrupt:
	udp_listener_running = False
	print("Closing.")