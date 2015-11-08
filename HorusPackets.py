#!/usr/bin/env python2.7
#
#   Project Horus 
#   Packet Parsers
#   Copyright 2015 Mark Jessop <vk5qi@rfhead.net>
#

import time, struct, json, socket

HORUS_UDP_PORT = 55672

# Packet Payload Types
class HORUS_PACKET_TYPES:
    PAYLOAD_TELEMETRY     = 0
    TEXT_MESSAGE          = 1
    CUTDOWN_COMMAND       = 2


# Some utilities to use in other programs.
def decode_payload_type(packet):
    # This expects the payload as an integer list. Convert it to one if it isn't already
    packet = list(bytearray(packet))

    # First byte of every packet is the payload type.
    payload_type = packet[0]

    return payload_type

def decode_payload_flags(packet):
    # This expects the payload as an integer list. Convert it to one if it isn't already
    packet = list(bytearray(packet))

    # Payload flags is always the second byte.
    payload_flags_byte = packet[1]
    payload_flags = {
        'src_addr'    : payload_flags_byte >> 4,          # Not currently used.
        'is_repeated' : payload_flags_byte >> 0 & 0x01,   # Indicates a packet repeated off a payload.
    }
    return payload_flags


# TEXT MESSAGE PACKET
# Payload Format:
# Byte 0 - Payload ID
# Byte 1 - Payload Flags
# Byte 2-9 - Callsign (Max 8 chars. Padded to 8 characters if shorter.)
# Bytes 10-63 - Message (Max 55 characters. Not padded!)
def create_text_message_packet(source="N0CALL", message="CQ CQ CQ"):
    # Sanitise input
    if len(source)>8:
        source = source[:8]

    if len(message)>54:
        message = message[:54]

    # Pad data if required.
    if len(source)<8:
        source = source + "\x00"*(8-len(source))

    packet = [HORUS_PACKET_TYPES.TEXT_MESSAGE,0] + list(bytearray(source)) + list(bytearray(message))
    return packet

def read_text_message_packet(packet):
    # Convert packet into a string, if it isn't one already.
    packet = str(bytearray(packet))
    source = packet[2:9].rstrip(' \t\r\n\0')
    message = packet[10:].rstrip('\n\0')
    return (source,message)

# Binary Payload Telemetry
binarypacketformat = "<BHHffHBBBB"
binarypacketlength = 19

def decode_horus_payload_telemetry(data):
    try:
        unpacked = struct.unpack(binarypacketformat, data)
    except:
        print "Wrong string length. Packet contents:"
        print ":".join("{:02x}".format(ord(c)) for c in data)
        return

    payload_id = unpacked[0]
    counter = unpacked[1]
    time_biseconds = unpacked[2]
    latitude = unpacked[3]
    longitude = unpacked[4]
    altitude = unpacked[5]
    speed = unpacked[6]
    batt_voltage = unpacked[7]
    sats = unpacked[8]
    temp = unpacked[9]


    time_string = time.strftime("%H:%M:%S", time.gmtime(time_biseconds*2))

    batt_voltage_float = 0.5 + 1.5*batt_voltage/255.0

    #print "Decoded Packet: %s  %f,%f %d %.2f %d" % (time_string, latitude, longitude, altitude, speed*1.852, sats)

    print "\n\nDecoded Packet: %s" % (":".join("{:02x}".format(ord(c)) for c in data))
    print "      ID: %d" % payload_id
    print " Seq No.: %d" % counter
    print "    Time: %s" % time_string
    print "     Lat: %.5f" % latitude
    print "     Lon: %.5f" % longitude
    print "     Alt: %d m" % altitude
    print "   Speed: %.1f kph" % (speed*1.852)
    print "    Sats: %d" % sats
    print "    Batt: %.3f" % batt_voltage_float
    print "    Temp: %d" % temp
    print " "


# UDP Helper Methods

def tx_packet(packet):
    packet = {
        'type' : 'TXPKT',
        'payload' : list(bytearray(packet))
    }
    print packet
    s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
    s.sendto(json.dumps(packet),('255.255.255.255',HORUS_UDP_PORT))
    s.close()
