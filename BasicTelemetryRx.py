#!/usr/bin/env python2.7
#
#   Project Horus 
#   Basic Telemetry RX
#   Copyright 2015 Mark Jessop <vk5qi@rfhead.net>
#
#	A quick hack to test the binary telemetry decoder.

from HorusPackets import *
import socket,json,sys,Queue

udp_listener_running = False

def process_udp(udp_packet):
	try:
		packet_dict = json.loads(udp_packet)
		
		print(udp_packet_to_string(packet_dict))
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
				process_udp(m[0])
	
	print("Closing UDP Listener")
	s.close()

try:
	udp_rx_thread()
except KeyboardInterrupt:
	print("Closing.")