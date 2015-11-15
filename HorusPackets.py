#!/usr/bin/env python2.7
#
#   Project Horus 
#   Packet Parsers
#   Copyright 2015 Mark Jessop <vk5qi@rfhead.net>
#

import time, struct, json, socket
from datetime import datetime

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
        'repeater_id'    : payload_flags_byte >> 4,     # Repeating payload inserts a unique ID in here
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


# PAYLOAD TELEMETRY PACKET
# This one is in a bit of flux at the moment.
# Payload Format:
# struct TBinaryPacket
# {
#   uint8_t   PacketType;
#   uint8_t   PayloadFlags;
#   uint8_t     PayloadIDs;
#   uint16_t    Counter;
#   uint16_t    BiSeconds;
#   float       Latitude;
#   float       Longitude;
#   uint16_t    Altitude;
#   uint8_t   Speed; // Speed in Knots (1-255 knots)
#   uint8_t   BattVoltage; // 0 = 0.5v, 255 = 2.0V, linear steps in-between.
#   uint8_t   Sats;
#   uint8_t   Temp; // Twos Complement Temp value.
# };  //  __attribute__ ((packed));

def decode_horus_payload_telemetry(packet):
    packet = str(bytearray(packet))

    horus_format_struct = "<BBBHHffHBBBB"
    try:
        unpacked = struct.unpack(horus_format_struct, packet)
    except:
        print "Wrong string length. Packet contents:"
        print ":".join("{:02x}".format(ord(c)) for c in data)
        return {}

    telemetry = {}
    telemetry['packet_type'] = unpacked[0]
    telemetry['payload_flags'] = unpacked[1]
    telemetry['payload_id'] = unpacked[2]
    telemetry['counter'] = unpacked[3]
    telemetry['time_biseconds'] = unpacked[4]
    telemetry['latitude'] = unpacked[5]
    telemetry['longitude'] = unpacked[6]
    telemetry['altitude'] = unpacked[7]
    telemetry['speed'] = unpacked[8]
    telemetry['batt_voltage_raw'] = unpacked[9]
    telemetry['sats'] = unpacked[10]
    telemetry['temp'] = unpacked[11]

    # Convert some of the fields into more useful units.
    telemetry['time'] = time.strftime("%H:%M:%S", time.gmtime(telemetry['time_biseconds']*2))
    telemetry['batt_voltage'] = 0.5 + 1.5*telemetry['batt_voltage_raw']/255.0

    return telemetry

# Transmit packet via UDP Broadcast
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

# Produce short string representation of packet payload contents.
def payload_to_string(packet):
    payload_type = decode_payload_type(packet)

    if payload_type == HORUS_PACKET_TYPES.PAYLOAD_TELEMETRY:
        telemetry = decode_horus_payload_telemetry(packet)
        data = "Balloon Telemetry: %s,%d,%.5f,%.5f,%d,%d" % (telemetry['time'],telemetry['counter'],
            telemetry['latitude'],telemetry['longitude'],telemetry['altitude'],telemetry['sats'])
        return data
    elif payload_type == HORUS_PACKET_TYPES.TEXT_MESSAGE:
        (source, message) = read_text_message_packet(packet)
        flags = decode_payload_flags(packet)
        if flags['is_repeated']:
            data = "Repeated Text Message: <%s> %s" % (source,message)
        else:
            data = "Text Message: <%s> %s" % (source,message)
        return data
    elif payload_type == HORUS_PACKET_TYPES.CUTDOWN_COMMAND:
        return "Cutdown Command: <Not Implemented>"
    else:
        return "Unknown Payload"

def udp_packet_to_string(udp_packet):
    try:
        pkt_type = udp_packet['type']
    except Exception as e:
        return "Unknown UDP Packet"

    if pkt_type == "RXPKT":
        timestamp = udp_packet['timestamp']
        rssi = float(udp_packet['rssi'])
        snr = float(udp_packet['snr'])
        crc_ok = udp_packet['pkt_flags']['crc_error'] == 0
        if crc_ok:
            payload_str = payload_to_string(udp_packet['payload'])
        else:
            payload_str = "CRC Fail!"
        return "%s RXPKT \tRSSI: %.1f SNR: %.1f \tPayload:[%s]" % (timestamp,rssi,snr,payload_str)
    elif pkt_type == "STATUS":
        timestamp = udp_packet['timestamp']
        rssi = float(udp_packet['rssi'])
        # Insert Modem Status decoding code here.
        return "%s STATUS \tRSSI: %.1f" % (timestamp,rssi)
    elif pkt_type == "TXPKT":
        timestamp = datetime.utcnow().isoformat()
        payload_str = payload_to_string(udp_packet['payload'])
        return "%s TXPKT \tPayload:[%s]" % (timestamp,payload_str)
    elif pkt_type == "TXDONE":
        timestamp = udp_packet['timestamp']
        payload_str = payload_to_string(udp_packet['payload'])
        return "%s TXDONE \tPayload:[%s]" % (timestamp,payload_str)
    elif pkt_type == "TXQUEUED":
        timestamp = udp_packet['timestamp']
        payload_str = payload_to_string(udp_packet['payload'])
        return "%s TXQUEUED \tPayload:[%s]" % (timestamp,payload_str)
    else:
        return "Not Implemented"