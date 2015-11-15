#!/usr/bin/env python2.7
#
#   Project Horus 
#   LoRa-UDP Gateway Server
#   Copyright 2015 Mark Jessop <vk5qi@rfhead.net>
#   
#   - Connects to and configures a LoRa receiver (SX127x family of ICs)
#   - Uses UDP broadcast (port 55672) to send/receive as json-encoded dicts:
#       - Receiver status updates (RSSI, SNR)
#       - Received packets. 
#   - Listens for json-encoded packets to be transmitted on the same port.
#       - Any received packets go into a queue to be transmitted when the channel is clear.
#
#   Dependencies
#   ============
#   Requires the modified version of pySX127x which lives here:
#   https://github.com/darksidelemm/pySX127x
#   This currently doesn't have any installer, so the SX127x folder will need to be dropped into
#   the current directory.
#
#   TODO
#   ====
#   [ ] Allow selection of hardware backend (RPi, SPI-UART Bridge) from command line arg.
#   [ ] Read LoRa configuration data (frequency, rate, etc) from a configuration file.
#   
#   
#   JSON PACKET FORMATS
#   ===================
#
#   TRANSMIT PACKET
#   Packet to be transmitted by the LoRa server. Is added to a queue and transmitted when channel is clear.
#   ---------------
#   transmit_packet = {
#       'type' : 'TXPKT',
#       'payload' : [<payload as a list of bytes>] # Encode this using list(bytearray('string'))
#   }
#
#   TRANSMIT CONFIRMATION
#   Sent when a packet has been transmitted.
#   ---------------------
#   tx_confirmation = {
#     'type' : 'TXDONE',
#     'timestamp' : '<ISO-8601 formatted timestamp>',
#     'payload' : [<payload as a list of bytes>]
#   }
#   
#   STATUS PACKET
#   Broadcast frequently (5Hz or so) to indicate current modem status, for RSSI plotting or similar.
#   -------------
#   status_packet = {
#       'type' : 'STATUS',
#       'timestamp : '<ISO-8601 formatted timestamp>',
#       'rssi' : <Current RSSI in dB>,
#       'status': {<Current Modem Status, straight from pySX127x's get_modem_status()}
#   }
#   
#   RX DATA PACKET
#   Broacast whenever a LoRa packet is received
#   Packets are sent out even if the CRC failed. CRC info is available in the 'pkt_flags' dict.
#   --------------
#   rx_data_packet = {
#     'type' : 'RXPKT',
#     'timestamp' : '<ISO-8601 formatted timestamp>',
#     'rssi' : <Current RSSI in dB>,
#     'snr'  : <Packet SNR in dB>,
#     'payload' : [<payload as a list of bytes>],
#     'pkt_flags' : {LoRa IRQ register flags at time of packet RX}# pkt_flags["crc_error"] == 0 if CRC is ok.
#   }
#

import json,socket,Queue,random, argparse, sys
from time import sleep
from threading import Thread
from HorusPackets import *
from datetime import *


from SX127x.LoRa import *
#from SX127x.LoRaArgumentParser import LoRaArgumentParser

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument("--rpishield", action="store_true")
group.add_argument("--spibridge", action="store_true")
args = parser.parse_args()

# Choose hardware interface
if args.spibridge:
    from SX127x.hardware_spibridge import HardwareInterface
elif args.rpishield:
    from SX127x.hardware_piloragateway import HardwareInterface
else:
    sys.exit(1)



class LoRaTxRxCont(LoRa):
    def __init__(self,hw,verbose=False):
        super(LoRaTxRxCont, self).__init__(hw,verbose)
        self.set_mode(MODE.SLEEP)
        self.set_dio_mapping([0] * 6)

        self.max_payload = 64

        self.udp_broadcast_port = 55672

        self.txqueue = Queue.Queue(16)
        self.udp_listener_running = False


    def set_common(self):
        self.set_mode(MODE.STDBY)
        self.set_freq(431.650)
        self.set_bw(BW.BW125)
        self.set_rx_crc(True)
        self.set_coding_rate(CODING_RATE.CR4_8)
        self.set_spreading_factor(10)
        self.set_max_payload_length(self.max_payload)
        self.set_hop_period(0xFF)
        self.set_implicit_header_mode(False)
        self.set_low_data_rate_optim(True)

    def set_rx_mode(self):
        self.set_lna_gain(GAIN.G1)
        self.set_pa_config(pa_select=0,max_power=0,output_power=0)
        self.set_agc_auto_on(True)
        self.set_detect_optimize(0x03)
        self.set_detection_threshold(0x0A)
        self.set_dio_mapping([0] * 6)
        self.set_mode(MODE.RXCONT)

    def set_tx_mode(self):
        self.set_lna_gain(GAIN.G6)
        self.set_pa_config(pa_select=1,max_power=0,output_power=0x0F) # 50mW

        self.set_mode(MODE.TX)

    def udp_broadcast(self,data):
        s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
        s.sendto(json.dumps(data),('255.255.255.255',self.udp_broadcast_port))
        s.close()

    def udp_send_rx(self,payload,snr,rssi,pkt_flags):
        pkt_dict = {
            "type"      :   "RXPKT",
            "timestamp" : datetime.utcnow().isoformat(),
            "payload"   :  payload,
            "snr"       :   snr,
            "rssi"      :   rssi,
            "pkt_flags" :    pkt_flags
        }
        self.udp_broadcast(pkt_dict)

    def on_rx_done(self):
        self.BOARD.led_on()
#        print("\nRxDone")
        pkt_flags = self.get_irq_flags()
        snr = self.get_pkt_snr_value()
        rssi = self.get_pkt_rssi_value()
#        print("Packet SNR: %.1f dB, RSSI: %d dB" % (snr, rssi))
        rxdata = self.read_payload(nocheck=True)
        print("RX Packet!")

        self.udp_send_rx(rxdata,snr,rssi,pkt_flags)

#        if pkt_flags["crc_error"] == 0:
#            print(map(hex, rxdata))
#            print("Payload: %s" %str(bytearray(rxdata)))
#            decode_binary_packet(str(bytearray(rxdata)))
#        else:
#            print("Packet Failed CRC!")
        self.set_mode(MODE.SLEEP)
        self.reset_ptr_rx()
        self.BOARD.led_off()
        # Go back into RX mode.
        self.set_rx_mode()

    def on_tx_done(self):
        print("\nTxDone")
        print(self.get_irq_flags())

    def tx_packet(self,data):
        # Clip payload to max_paload length.
        if len(data)>self.max_payload:
            data = data[:self.max_payload]

        print("Transmitting: %s" % data)
        # Write payload into fifo.
        self.set_mode(MODE.STDBY)
        self.set_lna_gain(GAIN.G6)
        self.set_pa_config(pa_select=1,max_power=0,output_power=0x0F) # 50mW
        self.set_dio_mapping([1,0,0,0,0,0])
        self.set_payload_length(len(data))
        self.write_payload(list(bytearray(data)))
        print(self.get_payload_length())
        # Transmit!
        tx_timestamp = datetime.utcnow().isoformat()
        print(datetime.utcnow().isoformat())
        self.set_mode(MODE.TX)
        # Busy-wait until tx_done is raised.
        print "Waiting for transmit to finish..."
        # For some reason, if we start reading the IRP flags immediately, the TX can
        # abort prematurely. Dunno why yet.
        sleep(1)
        # Can probably fix this by, y'know, using interrupt lines properly.
        #while(self.get_irq_flags()["tx_done"]==False):
        while(self.BOARD.read_gpio()[0] == 0):
            pass

        print(datetime.utcnow().isoformat())
        # Broadast a UDP packet indicating we have just transmitted.
        tx_indication = {
            'type'  : "TXDONE",
            'timestamp' : tx_timestamp,
            'payload' : list(bytearray(data))
        }
        self.udp_broadcast(tx_indication)

        #self.set_mode(MODE.STDBY)
        self.clear_irq_flags()
        self.set_rx_mode()
        print("Done.")

    # Perform some checks to see if the channel is free, then TX immediately.
    def attemptTX(self):
        # Check modem status a few times to be sure we aren't about to stomp on anyone.
        for x in range(5):
            status = self.get_modem_status()
            if status['signal_detected'] == 1:
                # Signal detected? Immediately return. Try again later.
                return
            else:
                sleep(random.random()*0.2) # Wait a random length of time.

        # If we get this far, we'll assume the channel is clear, and transmit.
        try:
            data = self.txqueue.get_nowait()
        except:
            return
        # Transmit!
        self.tx_packet(data)

    # Continuously listen on a UDP port for json data.
    # If a valid packet is received, put it in the transmit queue.
    # This function should be run in a separate thread.
    def udp_listen(self):
        s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        s.settimeout(1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('',self.udp_broadcast_port))
        print("Started UDP Listener Thread.")
        self.udp_listener_running = True
        while self.udp_listener_running:
            try:
                m = s.recvfrom(1024)
            except:
                pass

            if m != None:
                try:
                    m_data = json.loads(m[0])
                    if m_data['type'] == 'TXPKT':
                        self.txqueue.put_nowait(m_data['payload']) # TODO: Data type checking.
                except Exception as e:
                    print(e)
                    print("ERROR: Received Malformed UDP Packet")
        #
        print("Closing UDP Listener")
        s.close()

    def start(self):
        # Start up UDP listener thread.
        t = Thread(target=self.udp_listen)
        t.start()

        # Startup LoRa hardware
        self.reset_ptr_rx()
        self.set_common()
        self.set_rx_mode()
        # Main loop
        while True:
            sleep(0.05)
            rssi_value = self.get_rssi_value()
            status = self.get_modem_status()

            # Generate dictionary to broadcast
            status_dict = {
                'type'  : "STATUS",
                "timestamp" : datetime.utcnow().isoformat(),
                'rssi'  : rssi_value,
                'status': status
            }
            self.udp_broadcast(status_dict)

            #sys.stdout.flush()
            #sys.stdout.write("\r%d %d %d" % (rssi_value, status['rx_ongoing'], status['signal_detected']))

            #if(self.get_irq_flags()["rx_done"]==True):
            if(self.BOARD.read_gpio()[0] == 1):
                self.on_rx_done()

            if(self.txqueue.qsize()>0):
                # Something in the queue to be transmitted.
                self.attemptTX()


hw = HardwareInterface()
lora = LoRaTxRxCont(hw,verbose=False)
#lora.set_pa_config(max_power=0, output_power=0)

print(lora)
#assert(lora.get_agc_auto_on() == 1)


try:
    lora.start()
except KeyboardInterrupt:
    sys.stdout.flush()
    print("")
    sys.stderr.write("KeyboardInterrupt\n")
finally:
    sys.stdout.flush()
    print("")
    lora.set_mode(MODE.SLEEP)
    lora.udp_listener_running = False
    print(lora)
    print("Shutting down hardware interface...")
    hw.teardown()
    print("Done.")

