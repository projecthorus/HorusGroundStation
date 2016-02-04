#!/usr/bin/env python2.7
#
#   Project Horus 
#   Payload Telemetry Habitat Uploader
#   Copyright 2015 Mark Jessop <vk5qi@rfhead.net>
#
#	Again, another quick hack to test out the habitat upload functions added to HorusPackets.
#	This should also be useful in headless receiver situations.
#

from HorusPackets import *
from threading import Thread
from datetime import datetime
import socket,json,sys,argparse

udp_broadcast_port = HORUS_UDP_PORT
udp_listener_running = False

parser = argparse.ArgumentParser()
parser.add_argument("callsign", help="Listener Callsign")
parser.add_argument("-l","--log_file",default="telemetry.log",help="Log file for RX Telemetry")
args = parser.parse_args()

def write_log_entry(packet):
	timestamp = datetime.utcnow().isoformat()
	rssi = str(packet['rssi'])
	snr = str(packet['snr'])
	if packet['pkt_flags']['crc_error'] != 0:
		sentence = "CRC FAIL\n"
	else:
		if decode_payload_type(packet['payload']) == HORUS_PACKET_TYPES.PAYLOAD_TELEMETRY:
			telemetry = decode_horus_payload_telemetry(packet['payload'])
			sentence = telemetry_to_sentence(telemetry)
		else:
			sentence = "NOT TELEMETRY\n"

	log = open(args.log_file,'a')
	log_string = "%s,%s,%s,%s" % (timestamp,rssi,snr,sentence)
	print(log_string)
	log.write(log_string)
	log.close()


def process_udp(udp_packet):
	try:
		packet = json.loads(udp_packet)
		# Only process received telemetry packets.
		if packet['type'] != "RXPKT":
			return

		write_log_entry(packet)

		# Only upload packets that pass CRC (though we log if CRC failed)
		if packet['pkt_flags']['crc_error'] != 0:
			return

		payload = packet['payload']
		payload_type = decode_payload_type(payload)

		# Only process payload telemetry packets.
		if payload_type == HORUS_PACKET_TYPES.PAYLOAD_TELEMETRY:
			telemetry = decode_horus_payload_telemetry(payload)
			sentence = telemetry_to_sentence(telemetry)
			(success,error) = habitat_upload_payload_telemetry(telemetry,callsign=args.callsign)
			if success:
				print("Uploaded Successfuly!")
			else:
				print("Upload Failed: %s" % error)
		else:
			return
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

try:
	udp_rx_thread()
except KeyboardInterrupt:
	print("Closing.")