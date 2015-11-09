#!/usr/bin/env python2.7
#
#   Project Horus 
#   Basic Telemetry RX
#   Copyright 2015 Mark Jessop <vk5qi@rfhead.net>
#
#	A quick hack to test the binary telemetry decoder.

from HorusPackets import *
import socket,json,sys,Queue

def process_udp(udp_packet):
	try:
		packet_dict = json.loads(udp_packet)
		if packet_dict['pkt_flags']['crc_error'] == 1:
			return
		if packet_dict['type'] == 'RXPKT':
			if(packet_dict['payload'][0] == HORUS_PACKET_TYPES.PAYLOAD_TELEMETRY):
				print packet_dict['payload']
				telemetry = decode_horus_payload_telemetry(packet_dict['payload'])
				print(telemetry)
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

udp_rx_thread()