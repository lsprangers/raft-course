# client.py
# This is a very "stupid" client we just use to feed data into somewhere from CLI utils

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__name__)))

from socket import socket, AF_INET, SOCK_STREAM
from resources.socketInterface import SocketInterface
from resources.raftConfig import raftConfig
from resources.messageInterface import *
1

def get_leader():
    leader_node_id = input("Who is leader? >")
    
    leader_id = int(leader_node_id)

    leader_host = this_raftConfig.SERVERS[int(leader_id)][0]
    leader_port = this_raftConfig.SERVERS[int(leader_id)][1]
    return(leader_id, leader_host, leader_port)

this_raftConfig = raftConfig()
leader_id, leader_host, leader_port = get_leader()


while True:
    try:
        sock = socket(AF_INET, SOCK_STREAM)
        sock.connect((leader_host, leader_port))
    except ConnectionRefusedError:
        leader_id, leader_host, leader_port = get_leader()
        
    messager = SocketInterface()
    msg = input("Fling commands to leader >")
    if not msg:
        break
    
    if 'debug' in msg:
        outgoing_msg = Message(from_server_id=-1, to_server_id=leader_id, type=MessageTypes.DebugPrintLog, data=None)
    else:
        outgoing_msg = Message(from_server_id=-1, to_server_id=leader_id, type=MessageTypes.ClientCommand, data=ClientCommand(command=msg, hash=messager.hash_client_command(msg)))
        
    print(f"Sending {outgoing_msg.data} to leader")
    
    try:
        messager.send_message(sock=sock, msg=outgoing_msg)
        sock.close()
    except ConnectionRefusedError or BrokenPipeError:
        leader_id, leader_host, leader_port = get_leader()

    
