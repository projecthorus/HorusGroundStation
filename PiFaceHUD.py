#!/usr/bin/env python2.7
#
#   Project Horus 
#   PiFace Display Heads-Up Data
#   Used as a 'quick look' summary of basic payload statistics (alt, ascent rate, etc)
#   Copyright 2017 Mark Jessop <vk5qi@rfhead.net>
#

from HorusPackets import *
from threading import Thread
from datetime import datetime
import socket,json,sys,Queue,traceback,time,math
from earthmaths import *

udp_broadcast_port = HORUS_UDP_PORT
udp_listener_running = False

# RX Message queue to avoid threading issues.
rxqueue = Queue.Queue(16)

# Local Payload state variables.
payload_latitude = 0.0
payload_longitude = 0.0
payload_altitude = 0.0
payload_lastdata = -1
payload_data_age = 0

# Car state variables
car_latitude = 0.0
car_longitude = 0.0
car_altitude = 0.0
car_bearing = -1
car_speed = 0
car_lastdata = -1
car_data_age = 0

# Display Variables
azimuth_degrees = 0
elevation_degrees = 0
range_m = 0
speed_kph = 0
asc_rate_m = 0

cad = None

try:
    import pifacecad
    cad = pifacecad.PiFaceCAD()
    cad.lcd.backlight_on()
    cad.lcd.cursor_off()
    cad.lcd.blink_off()
except:
    print("Can't start PiFace. Continuing with debug output only.")

def update_lcd():
    global payload_altitude, speed_kph, asc_rate_m, azimuth_degrees, elevation_degrees, range_m, payload_data_age, car_data_age

#00000m H000 V00.0
#0.0km NNE 01 00.0

    if speed_kph > 99:
        speed_kph = 99
    line_1 = "%05dm H%02dV%02.1f" % (int(payload_altitude), int(speed_kph), asc_rate_m)
    
    if car_data_age > 20.0:
        line_2 = "%10s %2.1f" % ("NO GPS", payload_data_age)
    else:
        direction = bearing_to_cardinal(azimuth_degrees)
        if elevation_degrees < 0:
            elevation_degrees = 0
        range_km = range_m/1000.0
        if range_km >= 10:
            range_km = int(range_m/1000.0)
            line_2 = "%03dkm %3s %02d %2.1f" % (int(range_km), direction, int(elevation_degrees), payload_data_age)
        else:
            line_2 = "%04dm %3s %02d %2.1f" % (int(range_m), direction, int(elevation_degrees), payload_data_age)

    print(len(line_1))
    print(len(line_2))

    print("Updating Display:")
    print("%s\n%s" % (line_1, line_2))

    if cad != None:
        cad.lcd.write("%s\n%s" % (line_1, line_2))
        cad.lcd.home()


# Speed Calculation Should probably move this to another file.
def speed_calc(lat,lon,lat2,lon2,timediff):

    temp = position_info((lat,lon,0.0), (lat2,lon2,0.0))

    return (temp['great_circle_distance']/float(timediff))*3.6


def calculate_az_el_range():
    global payload_latitude, payload_longitude, payload_altitude, car_latitude, car_longitude, car_altitude, azimuth_degrees, elevation_degrees, range_m

    # Don't calculate anything if either the car or balloon data is invalid.
    if car_lastdata == -1:
        return

    if payload_lastdata == -1:
        return

    # Calculate az/el/range using the CUSF EarthMaths library.
    balloon_coords = position_info((car_latitude,car_longitude,car_altitude), (payload_latitude, payload_longitude, payload_altitude))
    azimuth_degrees = balloon_coords['bearing']
    elevation_degrees = balloon_coords['elevation']
    range_m = balloon_coords['straight_distance']

    

def update_payload_stats(packet):
    global payload_latitude, payload_longitude, payload_altitude, payload_lastdata, payload_data_age
    try:
        timestamp = time.time()
        time_diff = timestamp - payload_lastdata

        new_latitude = packet['latitude']
        new_longitude = packet['longitude']
        new_altitude = packet['altitude']

        asc_rate_m = (new_altitude - payload_altitude)/time_diff
        speed_kph = speed_calc(payload_latitude, payload_longitude, new_latitude, new_longitude, time_diff)

        # Save payload state values.
        payload_latitude = new_latitude
        payload_longitude = new_longitude
        payload_altitude = new_altitude
        payload_lastdata = timestamp
        payload_data_age = 0.0
        calculate_az_el_range()
        update_lcd()
    except:
        traceback.print_exc()

def update_car_stats(packet):
    global car_latitude, car_longitude, car_altitude, car_lastdata, car_data_age, car_bearing, car_speed
    try:
        timestamp = time.time()
        time_diff = timestamp - car_lastdata

        new_car_latitude = packet['latitude']
        new_car_longitude = packet['longitude']
        new_car_altitude = packet['altitude']

        car_speed = speed_calc(car_latitude,car_longitude, new_car_latitude, new_car_longitude,time_diff)

        if car_speed > 15:
            car_movement = position_info((car_latitude,car_longitude,car_altitude), (new_car_latitude,new_car_longitude,new_car_altitude))
            car_bearing = car_movement['bearing']

        car_latitude = new_car_latitude
        car_longitude = new_car_longitude
        car_altitude = new_car_altitude

        car_lastdata = timestamp
        car_data_age = 0.0
        calculate_az_el_range()
        update_lcd()
    except:
        traceback.print_exc()

# Method to process UDP packets.
def process_udp(udp_packet):
    try:
        packet_dict = json.loads(udp_packet)

        # TX Confirmation Packet?
        if packet_dict['type'] == 'PAYLOAD_SUMMARY':
            update_payload_stats(packet_dict)
        elif packet_dict['type'] == 'GPS':
            update_car_stats(packet_dict)
        else:
            print(".")
            pass
            #print("Got other packet type (%s)" % packet_dict['type'])

    except:
        traceback.print_exc()
        pass

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
            rxqueue.put_nowait(m[0])
    
    print("Closing UDP Listener")
    s.close()


def read_queue():
    global payload_data_age, car_data_age
    try:
        packet = rxqueue.get_nowait()
        process_udp(packet)
    except:
        pass

    # Update 'data age' text.
    payload_data_age += 0.1
    car_data_age += 0.1


## Start Qt event loop unless running in interactive mode or using pyside.
if __name__ == '__main__':
    
    t = Thread(target=udp_rx_thread)
    t.start()
    try:
        while True:
            read_queue()
            time.sleep(0.1)
    except:
        traceback.print_exc()
        udp_listener_running = False
