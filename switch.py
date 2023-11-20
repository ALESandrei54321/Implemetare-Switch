#!/usr/bin/python3
import sys
import struct
import wrapper
import threading
import time
from wrapper import recv_from_any_link, send_to_link, get_switch_mac, get_interface_name

MAC_table = {}
interface_cable_type = {}

root_BID = None
root_cost = 0
own_BID = None
root_port = None
port_states = {}
ports = {}

def parse_switch_config(sw_id):
    switch_config_file = f'configs/switch{sw_id}.cfg'

    with open(switch_config_file, 'r') as file:
        for line in file:
            tokens = line.split()
            if len(tokens) > 1:
                interface_name = tokens[0]
                cable_type = tokens[1]
                interface_cable_type[interface_name] = cable_type
            else:
                global own_BID
                own_BID = tokens[0]




def parse_ethernet_header(data):
    # Unpack the header fields from the byte array
    #dest_mac, src_mac, ethertype = struct.unpack('!6s6sH', data[:14])
    dest_mac = data[0:6]
    src_mac = data[6:12]
    
    # Extract ethertype. Under 802.1Q, this may be the bytes from the VLAN TAG
    ether_type = (data[12] << 8) + data[13]

    vlan_id = -1
    # Check for VLAN tag (0x8100 in network byte order is b'\x81\x00')
    if ether_type == 0x8200:
        vlan_tci = int.from_bytes(data[14:16], byteorder='big')
        vlan_id = vlan_tci & 0x0FFF  # extract the 12-bit VLAN ID
        ether_type = (data[16] << 8) + data[17]

    return dest_mac, src_mac, ether_type, vlan_id

def create_vlan_tag(vlan_id):
    # 0x8100 for the Ethertype for 802.1Q
    # vlan_id & 0x0FFF ensures that only the last 12 bits are used
    return struct.pack('!H', 0x8200) + struct.pack('!H', vlan_id & 0x0FFF)

def send_bdpu_every_sec(interfaces):
    
    while True:
        # TODO Send BDPU every second if necessary
        
        if root_BID == own_BID:
            BPDU_packet = (
                b'\x01\x80\xc2\x00\x00\x00' +  #BPDU multicast address
                get_switch_mac() +  #source address
                b'\x00\x38' +  #length
                b'\x42\x42\x03' + #DSAP + SSAP + control
                b'\x00\x00\x00\x00\x00' + #protocol info
                struct.pack('>Q', int(root_BID)) +
                struct.pack('>I', int(root_cost)) + 
                struct.pack('>Q', int(own_BID)) +
                b'\x00\x00\x00\x00' + #placeholder
                b'\x00\x00\x00\x00\x00\x00\x00\x00' #rest
            )
            for p in interfaces:
                if interface_cable_type[get_interface_name(p)] == 'T':
                    # Find the position in the BPDU_packet where the port bytes should be inserted
                    offset = len(BPDU_packet) - 12 #42
                    # Update BPDU with the port bytes
                    newBPDU = (
                        BPDU_packet[:offset] +
                        struct.pack('>I', p) +
                        BPDU_packet[offset + 4:]
                    )
                    forward_frame(newBPDU, p)

        time.sleep(1)

def forward_frame(frame, port):
    send_to_link(port, frame, len(frame))


def main():
    # init returns the max interface number. Our interfaces
    # are 0, 1, 2, ..., init_ret value + 1

    global root_BID
    global root_cost
    global root_port



    switch_id = sys.argv[1]

    parse_switch_config(switch_id)

    num_interfaces = wrapper.init(sys.argv[2:])
    interfaces = range(0, num_interfaces)

    #print("# Starting switch with id {}".format(switch_id), flush=True)
    #print("[INFO] Switch MAC", ':'.join(f'{b:02x}' for b in get_switch_mac()))

    for p in interfaces:
        name = get_interface_name(p)
        if interface_cable_type[name] == 'T':
            port_states[name] = 'BLOCKING'
            ports[name] = 'BLOCKED'
        else:
            port_states[name] = 'LISTENING'
            ports[name] = 'DESIGNATED'

    root_cost  = 0
    root_BID = own_BID

    if own_BID == root_BID:
        for i in interfaces:
            inter = get_interface_name(i)
            if interface_cable_type[inter] == 'T':
                ports[inter] = 'DESIGNATED'

    # Create and start a new thread that deals with sending BDPU
    t = threading.Thread(target=send_bdpu_every_sec, args=(interfaces, ))
    t.start()

    while True:
        # Note that data is of type bytes([...]).
        # b1 = bytes([72, 101, 108, 108, 111])  # "Hello"
        # b2 = bytes([32, 87, 111, 114, 108, 100])  # " World"
        # b3 = b1[0:2] + b[3:4].
        interface, data, length = recv_from_any_link()

        dest_mac, src_mac, ethertype, vlan_id = parse_ethernet_header(data)

        # print the MAC src and MAC dst in human readable format
        dest_mac_str = ':'.join(f'{b:02x}' for b in dest_mac)
        src_mac_str = ':'.join(f'{b:02x}' for b in src_mac)

        # Note. Adding a VLAN tag can be as easy as
        # tagged_frame = data[0:12] + create_vlan_tag(10) + data[12:]

        #print(f'Destination MAC: {dest_mac_str}')
        #print(f'Source MAC: {src_mac_str}')
        #print(f'EtherType: {ethertype}')

        #print("Received frame of size {} on interface {}".format(length, interface), flush=True)

        # TODO: Implement forwarding with learning
        # TODO: Implement VLAN support

        MAC_table[src_mac_str] = interface

        if dest_mac_str == '01:80:c2:00:00:00':
            sender_root_BID = int(struct.unpack('>Q', data[22:30])[0])
            sender_cost = int(struct.unpack('>I', data[30:34])[0])
            sender_BID = int(struct.unpack('>Q', data[34:42])[0])

            #print("Received Root BID:", sender_root_BID)
            #print("Received sender path cost:", sender_cost)
            #print("Received sender BID:", sender_BID)

            if sender_root_BID < int(root_BID):
                #print('Update root BID')
                old_BID = int(root_BID)
                root_BID = sender_root_BID
                root_cost = sender_cost + 10
                root_port = interface

                if old_BID == int(own_BID):
                    for i in interfaces:
                        if i != interface and interface_cable_type[get_interface_name(i)] == 'T':
                            port_states[get_interface_name(i)] = 'BLOCKING'
                            ports[get_interface_name(i)] = 'BLOCKED'
                
                port_states[get_interface_name(interface)] = 'LISTENING'

                for i in interfaces:
                    if i != interface and interface_cable_type[get_interface_name(i)] == 'T':
                        BPDU_packet = (
                            b'\x01\x80\xc2\x00\x00\x00' +  #BPDU multicast address
                            get_switch_mac() +  #source address
                            b'\x00\x38' +  #length
                            b'\x42\x42\x03' + #DSAP + SSAP + control
                            b'\x00\x00\x00\x00\x00' + #protocol info
                            struct.pack('>Q', int(root_BID)) +
                            struct.pack('>I', int(root_cost)) + 
                            struct.pack('>Q', int(own_BID)) +
                            struct.pack('>I', i) + 
                            b'\x00\x00\x00\x00\x00\x00\x00\x00' #rest
                        )
                        forward_frame(BPDU_packet, i)

            elif sender_root_BID == int(root_BID):
                if root_port == interface and sender_cost + 10 < root_cost:
                    root_cost = sender_cost + 10

                elif root_port != interface:
                    if sender_cost > root_cost:
                        inter = get_interface_name(interface)
                        ports[inter] = 'DESIGNATED'
                        port_states[inter] = 'LISTENING'

            elif sender_BID == int(own_BID):
                port_states[get_interface_name(interface)] = 'BLOCKING'
                ports[get_interface_name(interface)] = 'BLOCKED'
            else:
                pass

            
            if int(own_BID) == int(root_BID):
                for i in interfaces:
                    inter = get_interface_name(i)
                    if interface_cable_type[inter] == 'T':
                        ports[inter] = 'DESIGNATED'

        elif vlan_id != -1:
            # VLAN tagged frame
            if dest_mac_str[1] not in {'13579bdf'}:
                if dest_mac_str in MAC_table:
                    dest_interface = MAC_table[dest_mac_str]
                    if interface_cable_type[get_interface_name(dest_interface)] == 'T':
                        forward_frame(data, dest_interface)
                    else:
                        if interface_cable_type[get_interface_name(dest_interface)] == str(vlan_id):
                            forward_frame(data[0:12] + data[16:], dest_interface)
                else:
                    for o in interfaces:
                        if o != interface and ports[get_interface_name(o)] != 'BLOCKED':
                            name = get_interface_name(o)
                            if interface_cable_type[name] == str(vlan_id):
                                forward_frame(data[0:12] + data[16:], o)
                            elif interface_cable_type[name] == 'T':
                                forward_frame(data, o)
            else:
                for o in interfaces:
                    if o != interface and ports[get_interface_name(o)] != 'BLOCKED':
                        name = get_interface_name(o)
                        if interface_cable_type[name] == str(vlan_id):
                            forward_frame(data[0:12] + data[16:], o)
                        elif interface_cable_type[name] == 'T':
                            forward_frame(data, o)

        else: # no VLAN
            sender_vlan = interface_cable_type[get_interface_name(interface)]
            if dest_mac_str[1] not in {'13579bdf'}:
                if dest_mac_str in MAC_table:
                    dest_interface = MAC_table[dest_mac_str]
                    if interface_cable_type[get_interface_name(dest_interface)] == 'T':
                        forward_frame(data[0:12] + create_vlan_tag(int(sender_vlan)) + data[12:], dest_interface)
                    else:
                        if interface_cable_type[get_interface_name(dest_interface)] == str(sender_vlan):
                            forward_frame(data, dest_interface)
                else:
                    for o in interfaces:
                        if o != interface and ports[get_interface_name(o)] != 'BLOCKED': 
                            name = get_interface_name(o)
                            if interface_cable_type[name] == str(sender_vlan):
                                forward_frame(data, o)
                            elif interface_cable_type[name] == 'T':
                                forward_frame(data[0:12] + create_vlan_tag(int(sender_vlan)) + data[12:] , o)
            else:
                for o in interfaces:
                    if o != interface and ports[get_interface_name(o)] != 'BLOCKED':
                        name = get_interface_name(o)
                        if interface_cable_type[name] == str(sender_vlan):
                            forward_frame(data, o)
                        elif interface_cable_type[name] == 'T':
                            forward_frame(data[0:12] + create_vlan_tag(int(sender_vlan)) + data[12:], o)


        # TODO: Implement STP support

        # data is of type bytes.
        # send_to_link(i, data, length)

if __name__ == "__main__":
    main()
