#!/usr/bin/env python2.7
#
#   Project Horus 
#   Packet Parsers
#   Copyright 2015 Mark Jessop <vk5qi@rfhead.net>
#

import time, struct, json, socket, httplib, crcmod, urllib, urllib2
from base64 import b64encode
from hashlib import sha256
from datetime import datetime

HORUS_UDP_PORT = 55672
HORUS_OZIPLOTTER_PORT = 8942
MAX_JSON_LEN = 2048
TX_QUEUE_SIZE = 32

# Packet Payload Types
class HORUS_PACKET_TYPES:
    PAYLOAD_TELEMETRY     = 0
    TEXT_MESSAGE          = 1
    CUTDOWN_COMMAND       = 2
    PARAMETER_CHANGE      = 3
    COMMAND_ACK           = 4
    # Accept SSDV packets 'as-is'. https://ukhas.org.uk/guides:ssdv
    SSDV_FEC              = 0x66
    SSDV_NOFEC            = 0x67

class HORUS_PAYLOAD_PARAMS:
    PING                  = 0
    LISTEN_TIME           = 1


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

# SSDV Packets
# Generally we will just send this straight out to ssdv.habhub.org
def read_ssdv_packet_info(packet):
    packet = list(bytearray(packet))
    # Check packet is actually a SSDV packet.
    if len(packet) != 255:
        return "SSDV: Invalid Length"


    # We got this far, may as well try and extract the packet info.
    callsign = "???"
    packet_type = "FEC" if (packet[0]==0x66) else "No-FEC"
    image_id = packet[5]
    packet_id = (packet[6]<<8) + packet[7]
    width = packet[8]*16
    height = packet[9]*16

    return "SSDV: %s, Img:%d, Pkt:%d, %dx%d" % (packet_type,image_id,packet_id,width,height)

def upload_ssdv_packet(packet, callsign="N0CALL"):
    packet = "\x55" + str(bytearray(packet))
    hexpacket = "".join(x.encode('hex') for x in packet)
    url = "http://www.sanslogic.co.uk/ssdv/data.php"
    values = {'callsign':callsign,
        'encoding':'hex',
        'packet':data}
    valuedata = urllib.urlencode(values)
    req = urllib2.Request(url,valuedata)
    try:
        response = urllib2.urlopen(req)
        return (True,"OK")
    except Exception as e:
        return (False,"Failed to upload SSDV to Habitat: %s" % (str(e)))

# PAYLOAD TELEMETRY PACKET
# This one is in a bit of flux at the moment.
# Payload Format:
# struct TBinaryPacket
# {
#   uint8_t   PacketType;
#   uint8_t   PayloadFlags;
#     uint8_t     PayloadIDs;
#     uint16_t    Counter;
#     uint16_t    BiSeconds;
#     float       Latitude;
#     float       Longitude;
#     uint16_t    Altitude;
#   uint8_t   Speed; // Speed in Knots (1-255 knots)
#   uint8_t   Sats;
#   uint8_t   Temp; // Twos Complement Temp value.
#   uint8_t   BattVoltage; // 0 = 0.5v, 255 = 2.0V, linear steps in-between.
#   uint8_t   PyroVoltage; // 0 = 0v, 255 = 5.0V, linear steps in-between.
#   uint8_t   rxPktCount; // RX Packet Count.
#   uint8_t   rxRSSI; // Ambient RSSI value, measured just before transmission.
#   uint8_t   telemFlags; // Various payload flags, TBD
# };  //  __attribute__ ((packed));

def decode_horus_payload_telemetry(packet):
    packet = str(bytearray(packet))

    horus_format_struct = "<BBBHHffHBBBBBBBB"
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
    telemetry['sats'] = unpacked[9]
    telemetry['temp'] = unpacked[10]
    telemetry['batt_voltage_raw'] = unpacked[11]
    telemetry['pyro_voltage_raw'] = unpacked[12]
    telemetry['rxPktCount'] = unpacked[13]
    telemetry['RSSI'] = unpacked[14]-164
    telemetry['telemFlags'] = unpacked[15]

    # Convert some of the fields into more useful units.
    telemetry['time'] = time.strftime("%H:%M:%S", time.gmtime(telemetry['time_biseconds']*2))
    telemetry['batt_voltage'] = 0.5 + 1.5*telemetry['batt_voltage_raw']/255.0
    telemetry['pyro_voltage'] = 5.0*telemetry['pyro_voltage_raw']/255.0

    return telemetry

# Convert telemetry dictionary to a Habitat-compatible telemetry string.
# The below is compatible with genpayload doc ID# f18a873592a77ed01ea432c3bcc16d0f
def telemetry_to_sentence(telemetry):
    sentence = "$$HORUSLORA,%d,%s,%.5f,%.5f,%d,%d,%d,%.2f,%.2f,%d,%d" % (telemetry['counter'],telemetry['time'],telemetry['latitude'],
        telemetry['longitude'],telemetry['altitude'],telemetry['speed'],telemetry['sats'],telemetry['batt_voltage'],
        telemetry['pyro_voltage'],telemetry['RSSI'],telemetry['rxPktCount'])

    checksum = crc16_ccitt(sentence[2:])
    output = sentence + "*" + checksum + "\n"
    return output

# CRC16 function for the above.
def crc16_ccitt(data):
    """
    Calculate the CRC16 CCITT checksum of *data*.
    
    (CRC16 CCITT: start 0xFFFF, poly 0x1021)
    """
    crc16 = crcmod.predefined.mkCrcFun('crc-ccitt-false')
    return hex(crc16(data))[2:].upper().zfill(4)

# Command ACK Packet. Sent by the payload to acknowledge a command (i.e. cutdown or param change) has been executed.
def decode_command_ack(packet):
    packet = list(bytearray(packet))
    if len(packet) != 7:
        print "Invalid length for Command ACK."
        return {}

    ack_packet = {}
    ack_packet['rssi'] = packet[2] - 164
    ack_packet['snr'] = struct.unpack('b',str(bytearray([packet[3]])))[0]/4.
    if packet[4] == HORUS_PACKET_TYPES.CUTDOWN_COMMAND:
        ack_packet['command'] = "Cutdown"
        ack_packet['argument'] = "%d Seconds." % packet[5]
    elif packet[4] == HORUS_PACKET_TYPES.PARAMETER_CHANGE:
        ack_packet['command'] = "Param Change"
        ack_packet['argument'] = "%d %d" % (packet[5], packet[6])
        ack_packet['param'] = packet[5]
        ack_packet['value'] = packet[6]

    return ack_packet

def create_cutdown_packet(time=4,passcode="zzz"):
    if len(passcode)<3: # Pad out passcode. This will probably cause the payload not to accept it though.
        passcode = passcode + "   "

    # Sanitize cut time.
    if time>10:
        time = 10
    if time<0:
        time = 0

    cutdown_packet = [HORUS_PACKET_TYPES.CUTDOWN_COMMAND,0,0,0,0,0]
    cutdown_packet[2] = ord(passcode[0])
    cutdown_packet[3] = ord(passcode[1])
    cutdown_packet[4] = ord(passcode[2])
    cutdown_packet[5] = time

    return cutdown_packet

def create_param_change_packet(param = HORUS_PAYLOAD_PARAMS.PING, value = 10, passcode = "zzz"):
    if len(passcode)<3: # Pad out passcode. This will probably cause the payload not to accept it though.
        passcode = passcode + "   "
    # Sanitize parameter and value inputs.
    if param>255:
        param = 255

    if value>255:
        value = 255

    param_packet = [HORUS_PACKET_TYPES.PARAMETER_CHANGE,0,0,0,0,0,0]
    param_packet[2] = ord(passcode[0])
    param_packet[3] = ord(passcode[1])
    param_packet[4] = ord(passcode[2])
    param_packet[5] = param
    param_packet[6] = value

    return param_packet

# Transmit packet via UDP Broadcast
def tx_packet(payload,blocking=False,timeout=4):
    packet = {
        'type' : 'TXPKT',
        'payload' : list(bytearray(payload))
    }
    # Print some info about the packet.
    print packet
    print len(json.dumps(packet))
    # Set up our UDP socket
    s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    s.settimeout(1)
    # Set up socket for broadcast, and allow re-use of the address
    s.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('',HORUS_UDP_PORT))
    try:
        s.sendto(json.dumps(packet), ('<broadcast>', HORUS_UDP_PORT))
    except socket.error:
        s.sendto(json.dumps(packet), ('127.0.0.1', HORUS_UDP_PORT))

    if blocking:
        start_time = time.time() # Start time for our timeout.

        while (time.time()-start_time) < timeout:
            try:
                print("Waiting for UDP")
                (m,a) = s.recvfrom(MAX_JSON_LEN)
            except socket.timeout:
                m = None
            
            if m != None:
                try:
                    packet = json.loads(m)
                    if packet['type'] == 'TXDONE':
                        if packet['payload'] == list(bytearray(payload)):
                            print("Packet Transmitted Successfuly!")
                            s.close()
                            return
                        else:
                            print("Not our payload!")
                    else:
                        print("Wrong Packet: %s" % packet['type'])
                except Exception as e:
                    print("Error: %s" % e)
            else:
                print("Got no packet")
        print("TX Timeout!")

    else:
        s.close()



# Produce short string representation of packet payload contents.
def payload_to_string(packet):
    payload_type = decode_payload_type(packet)

    if payload_type == HORUS_PACKET_TYPES.PAYLOAD_TELEMETRY:
        telemetry = decode_horus_payload_telemetry(packet)
        data = "Balloon Telemetry: %s,%d,%.5f,%.5f,%d,%d,%.2f,%.2f,%d,%d" % (telemetry['time'],telemetry['counter'],
            telemetry['latitude'],telemetry['longitude'],telemetry['altitude'],telemetry['sats'],telemetry['batt_voltage'],telemetry['pyro_voltage'],telemetry['rxPktCount'],telemetry['RSSI'])
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
        return "Cutdown Command"

    elif payload_type == HORUS_PACKET_TYPES.COMMAND_ACK:
        ack = decode_command_ack(packet)
        data = "Command ACK: [R: %d dBm, S:%.1fdB] %s %s" % (ack['rssi'], ack['snr'], ack['command'], ack['argument'])
        return data
    elif payload_type == HORUS_PACKET_TYPES.PARAMETER_CHANGE:
        return "Parameter Change"
    elif (payload_type == HORUS_PACKET_TYPES.SSDV_FEC) or (payload_type == HORUS_PACKET_TYPES.SSDV_NOFEC):
        return read_ssdv_packet_info(packet)

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

        freq_error = float(udp_packet['freq_error'])
        crc_ok = udp_packet['pkt_flags']['crc_error'] == 0
        if crc_ok:
            payload_str = payload_to_string(udp_packet['payload'])
        else:
            payload_str = "CRC Fail!"
        return "%s RXPKT \tRSSI: %.1f SNR: %.1f FERR: %.1f \tPayload:[%s]" % (timestamp,rssi,snr,freq_error,payload_str)
    elif pkt_type == "STATUS":
        timestamp = udp_packet['timestamp']
        rssi = float(udp_packet['rssi'])
        txqueuesize = udp_packet['txqueuesize']
        # Insert Modem Status decoding code here.
        return "%s STATUS \tRSSI: %.1f \tQUEUE: %d" % (timestamp,rssi,txqueuesize)
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

# Habitat Upload Functions
def habitat_upload_payload_telemetry(telemetry, callsign="N0CALL"):
    sentence = telemetry_to_sentence(telemetry)

    sentence_b64 = b64encode(sentence)

    date = datetime.utcnow().isoformat("T") + "Z"

    data = {
        "type": "payload_telemetry",
        "data": {
            "_raw": sentence_b64
            },
        "receivers": {
            callsign: {
                "time_created": date,
                "time_uploaded": date,
                },
            },
    }
    try:
        c = httplib.HTTPConnection("habitat.habhub.org",timeout=4)
        c.request(
            "PUT",
            "/habitat/_design/payload_telemetry/_update/add_listener/%s" % sha256(sentence_b64).hexdigest(),
            json.dumps(data),  # BODY
            {"Content-Type": "application/json"}  # HEADERS
            )

        response = c.getresponse()
        return (True,"OK")
    except Exception as e:
        return (False,"Failed to upload to Habitat: %s" % (str(e)))

# OziPlotter Upload Functions
def oziplotter_upload_telemetry(telemetry,hostname="127.0.0.1"):
    sentence = telemetry_to_sentence(telemetry)

    try:
        ozisock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        ozisock.sendto(sentence,(hostname,HORUS_OZIPLOTTER_PORT))
        ozisock.close()
    except Exception as e:
        print("Failed to send to Ozi: " % e)

